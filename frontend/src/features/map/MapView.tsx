import * as maplibregl from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { useEffect, useRef, useState } from "react";
import hr from "../../i18n/hr.json";
import type { AirStation } from "../../lib/api/client";
import {
  BASEMAP_STYLE,
  CROATIA_BOUNDS,
  EAQI_COLORS,
  MAP_LAYERS,
  dataSources,
  riskColor,
  riskFilter,
} from "./layers";
import type { Bbox, Overlay, RiskLayer } from "./urlState";

// The published worker imports a shared chunk, so Vite has to bundle it into one file.
maplibregl.setWorkerUrl(workerUrl);

const COMPACT_ATTRIBUTION_WIDTH = 768;

const FALLBACK_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    {
      id: "background",
      type: "background",
      paint: { "background-color": "#f1f5f9" },
    },
  ],
};

interface Props {
  layer: RiskLayer;
  overlays: Overlay[];
  view: { lat: number; lon: number; zoom: number } | null;
  bbox: Bbox | null;
  pin: { lat: number; lon: number } | null;
  attribution: string;
  stations?: AirStation[];
  interactive?: boolean;
  onViewChange?: (view: { lat: number; lon: number; zoom: number }) => void;
  onPick?: (point: { lat: number; lon: number }) => void;
}

function stationFeatures(stations: AirStation[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: stations
      .filter(
        (station) =>
          station.lat != null && station.lon != null && !station.stale,
      )
      .map((station) => ({
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: [station.lon as number, station.lat as number],
        },
        properties: {
          name: station.name,
          color: station.eaqi_class
            ? EAQI_COLORS[station.eaqi_class - 1]
            : null,
        },
      })),
  };
}

function addDataLayers(
  map: maplibregl.Map,
  overlays: Overlay[],
  layer: RiskLayer,
): void {
  for (const [id, source] of Object.entries(dataSources())) {
    if (!map.getSource(id)) map.addSource(id, source);
  }
  for (const { overlay, ...spec } of MAP_LAYERS) {
    if (map.getLayer(spec.id)) continue;
    const visible = !overlay || overlays.includes(overlay);
    map.addLayer({
      ...spec,
      layout: { ...spec.layout, visibility: visible ? "visible" : "none" },
    } as maplibregl.LayerSpecification);
  }
  applyRiskLayer(map, layer);
}

function applyRiskLayer(map: maplibregl.Map, layer: RiskLayer): void {
  if (!map.getLayer("risk-fill")) return;
  map.setPaintProperty("risk-fill", "fill-color", riskColor(layer));
  map.setFilter("risk-fill", riskFilter(layer));
  map.setLayoutProperty(
    "risk-jls-fill",
    "visibility",
    layer === "ikr" ? "visible" : "none",
  );
}

export function MapView({
  layer,
  overlays,
  view,
  bbox,
  pin,
  attribution,
  stations,
  interactive = true,
  onViewChange,
  onPick,
}: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markerRef = useRef<maplibregl.Marker | null>(null);
  const attributionRef = useRef<maplibregl.AttributionControl | null>(null);
  const latest = useRef({ layer, overlays, onViewChange, onPick, stations });
  latest.current = { layer, overlays, onViewChange, onPick, stations };
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: BASEMAP_STYLE,
      bounds: view ? undefined : (bbox ?? CROATIA_BOUNDS),
      center: view ? [view.lon, view.lat] : undefined,
      zoom: view?.zoom,
      fitBoundsOptions: { padding: 24 },
      attributionControl: false,
      dragRotate: false,
      interactive,
    });
    map.touchZoomRotate.disableRotation();
    if (interactive) {
      map.addControl(
        new maplibregl.NavigationControl({ showCompass: false }),
        "bottom-right",
      );
    }
    mapRef.current = map;

    let usingFallback = false;
    map.on("style.load", () => {
      addDataLayers(map, latest.current.overlays, latest.current.layer);
      const source = map.getSource("stations") as
        maplibregl.GeoJSONSource | undefined;
      if (source && latest.current.stations) {
        source.setData(stationFeatures(latest.current.stations));
      }
    });
    map.on("error", (event) => {
      const message = String(event.error?.message ?? "");
      if (message.includes("/tiles/") && !message.includes("openfreemap")) {
        setNotice(hr.map.tilesError);
      } else if (!map.isStyleLoaded() && !usingFallback) {
        // The demo must not stay empty when the basemap host is unreachable.
        usingFallback = true;
        setNotice(hr.map.basemapError);
        map.setStyle(FALLBACK_STYLE);
      }
    });
    map.on("moveend", () => {
      const center = map.getCenter();
      latest.current.onViewChange?.({
        lat: center.lat,
        lon: center.lng,
        zoom: map.getZoom(),
      });
    });
    map.on("click", (event) => {
      latest.current.onPick?.({ lat: event.lngLat.lat, lon: event.lngLat.lng });
    });
    return () => {
      map.remove();
      mapRef.current = null;
      markerRef.current = null;
      attributionRef.current = null;
    };
    // The map is created once; later prop changes are applied by the effects below.
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (attributionRef.current) map.removeControl(attributionRef.current);
    const control = new maplibregl.AttributionControl({
      compact: window.innerWidth < COMPACT_ATTRIBUTION_WIDTH,
      customAttribution: attribution,
    });
    map.addControl(control, "bottom-left");
    attributionRef.current = control;
  }, [attribution]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      for (const { id, overlay } of MAP_LAYERS) {
        if (overlay && map.getLayer(id)) {
          map.setLayoutProperty(
            id,
            "visibility",
            overlays.includes(overlay) ? "visible" : "none",
          );
        }
      }
      applyRiskLayer(map, layer);
    };
    if (map.getLayer("risk-fill")) apply();
    else map.once("style.load", apply);
  }, [layer, overlays]);

  useEffect(() => {
    const source = mapRef.current?.getSource("stations") as
      maplibregl.GeoJSONSource | undefined;
    if (source && stations) source.setData(stationFeatures(stations));
  }, [stations]);

  useEffect(() => {
    if (bbox) {
      mapRef.current?.fitBounds(bbox, {
        padding: 48,
        maxZoom: 14,
        duration: 600,
      });
    }
  }, [bbox]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    markerRef.current?.remove();
    markerRef.current = null;
    if (pin) {
      const marker = new maplibregl.Marker({ color: "#0f172a" })
        .setLngLat([pin.lon, pin.lat])
        .addTo(map);
      marker.getElement().setAttribute("aria-label", hr.map.selected);
      markerRef.current = marker;
    }
  }, [pin]);

  return (
    <div className="absolute inset-0">
      <div
        ref={container}
        // Sized by height and width: MapLibre's CSS sets position: relative on this element.
        className="h-full w-full"
        role="region"
        aria-label={hr.map.label}
        data-testid="map"
      />
      {notice && (
        <p
          role="status"
          className="absolute bottom-20 left-1/2 z-10 w-[min(90%,28rem)] -translate-x-1/2 rounded bg-amber-100 px-3 py-2 text-sm text-amber-950 shadow"
        >
          {notice}
        </p>
      )}
    </div>
  );
}
