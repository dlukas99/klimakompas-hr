import * as maplibregl from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { useEffect, useRef, useState } from "react";
import hr from "../../i18n/hr.json";
import {
  BASEMAP_STYLE,
  CLICKABLE_LAYERS,
  CROATIA_BOUNDS,
  MAP_LAYERS,
  dataSources,
} from "./layers";
import type { Bbox, LayerId } from "./urlState";

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

export interface MapSelection {
  kind: "jls" | "cell";
  properties: Record<string, unknown>;
}

interface Props {
  layers: LayerId[];
  view: { lat: number; lon: number; zoom: number } | null;
  bbox: Bbox | null;
  pin: { lat: number; lon: number } | null;
  attribution: string;
  onViewChange: (view: { lat: number; lon: number; zoom: number }) => void;
  onSelect: (selection: MapSelection[]) => void;
}

function addDataLayers(map: maplibregl.Map, visible: LayerId[]): void {
  for (const [id, source] of Object.entries(dataSources())) {
    if (!map.getSource(id)) map.addSource(id, source);
  }
  for (const { group, ...layer } of MAP_LAYERS) {
    if (!map.getLayer(layer.id)) {
      map.addLayer({
        ...layer,
        layout: {
          ...layer.layout,
          visibility: visible.includes(group) ? "visible" : "none",
        },
      } as maplibregl.LayerSpecification);
    }
  }
}

export function MapView({
  layers,
  view,
  bbox,
  pin,
  attribution,
  onViewChange,
  onSelect,
}: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markerRef = useRef<maplibregl.Marker | null>(null);
  const attributionRef = useRef<maplibregl.AttributionControl | null>(null);
  const latest = useRef({ layers, onViewChange, onSelect });
  latest.current = { layers, onViewChange, onSelect };
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: BASEMAP_STYLE,
      bounds: view ? undefined : CROATIA_BOUNDS,
      center: view ? [view.lon, view.lat] : undefined,
      zoom: view?.zoom,
      fitBoundsOptions: { padding: 24 },
      attributionControl: false,
      dragRotate: false,
    });
    map.touchZoomRotate.disableRotation();
    map.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
      "bottom-right",
    );
    mapRef.current = map;

    let usingFallback = false;
    map.on("style.load", () => addDataLayers(map, latest.current.layers));
    map.on("error", (event) => {
      const message = String(event.error?.message ?? "");
      if (message.includes("/tiles/")) {
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
      latest.current.onViewChange({
        lat: center.lat,
        lon: center.lng,
        zoom: map.getZoom(),
      });
    });
    map.on("click", (event) => {
      const active = CLICKABLE_LAYERS.filter((id) => map.getLayer(id));
      const features = map.queryRenderedFeatures(event.point, {
        layers: active,
      });
      latest.current.onSelect(
        features.map((feature) => ({
          kind: feature.layer.id === "jls-hit" ? "jls" : "cell",
          properties: feature.properties,
        })),
      );
    });
    for (const id of CLICKABLE_LAYERS) {
      map.on(
        "mouseenter",
        id,
        () => (map.getCanvas().style.cursor = "pointer"),
      );
      map.on("mouseleave", id, () => (map.getCanvas().style.cursor = ""));
    }
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
      for (const { id, group } of MAP_LAYERS) {
        if (map.getLayer(id)) {
          map.setLayoutProperty(
            id,
            "visibility",
            layers.includes(group) ? "visible" : "none",
          );
        }
      }
    };
    if (map.isStyleLoaded()) apply();
    else map.once("idle", apply);
  }, [layers]);

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
      const marker = new maplibregl.Marker({ color: "#b91c1c" })
        .setLngLat([pin.lon, pin.lat])
        .addTo(map);
      marker.getElement().setAttribute("aria-label", hr.map.selected);
      markerRef.current = marker;
      map.flyTo({
        center: [pin.lon, pin.lat],
        zoom: Math.max(map.getZoom(), 15),
        duration: 600,
      });
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
          className="absolute top-3 left-1/2 z-10 w-[min(90%,28rem)] -translate-x-1/2 rounded bg-amber-100 px-3 py-2 text-sm text-amber-950 shadow"
        >
          {notice}
        </p>
      )}
    </div>
  );
}
