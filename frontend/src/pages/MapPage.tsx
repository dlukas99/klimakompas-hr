import { useCallback, useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { SearchBox } from "../components/SearchBox";
import hr from "../i18n/hr.json";
import type { GeocodeResult } from "../lib/api/client";
import { searchResultParams } from "../features/map/mapLink";
import { MapPanel } from "../features/map/MapPanel";
import { MapView, type MapSelection } from "../features/map/MapView";
import {
  parseMapUrl,
  serializeMapUrl,
  type LayerId,
} from "../features/map/urlState";
import { useSources } from "../features/map/useSources";

// The basemap style brings its own OpenStreetMap attribution.
const ATTRIBUTION_SOURCES = [
  "dgu_au",
  "dzs_naselja_2021",
  "estat_census_grid_2021",
];

export function MapPage() {
  const [params, setParams] = useSearchParams();
  const state = useMemo(() => parseMapUrl(params), [params]);
  const [selection, setSelection] = useState<MapSelection[]>([]);
  const { data: sources } = useSources();

  const attribution = useMemo(
    () =>
      (sources ?? [])
        .filter((source) => ATTRIBUTION_SOURCES.includes(source.id))
        .map((source) => source.attribution)
        .join(" · "),
    [sources],
  );

  const onViewChange = useCallback(
    (view: { lat: number; lon: number; zoom: number }) => {
      // The URL is read directly, so a late moveend cannot undo a layer change not yet rendered.
      const current = parseMapUrl(new URLSearchParams(window.location.search));
      setParams(serializeMapUrl({ ...current, view, bbox: null }), {
        replace: true,
      });
    },
    [setParams],
  );

  function toggleLayer(layer: LayerId) {
    const current = parseMapUrl(new URLSearchParams(window.location.search));
    const layers = current.layers.includes(layer)
      ? current.layers.filter((item) => item !== layer)
      : [...current.layers, layer];
    setParams(serializeMapUrl({ ...current, layers }), { replace: true });
  }

  function onSearch(result: GeocodeResult) {
    setParams(searchResultParams(result, params));
  }

  return (
    <div className="absolute inset-0">
      <ErrorBoundary message={hr.map.unavailable}>
        <MapView
          layers={state.layers}
          view={state.view}
          bbox={state.bbox}
          pin={state.pin}
          attribution={attribution}
          onViewChange={onViewChange}
          onSelect={setSelection}
        />
      </ErrorBoundary>
      <div className="pointer-events-none absolute inset-x-3 top-3 z-20 flex justify-end">
        <div className="pointer-events-auto w-full max-w-sm max-md:mt-11">
          <SearchBox onSelect={onSearch} />
        </div>
      </div>
      <MapPanel
        layers={state.layers}
        onToggle={toggleLayer}
        selection={selection}
        onClearSelection={() => setSelection([])}
      />
    </div>
  );
}
