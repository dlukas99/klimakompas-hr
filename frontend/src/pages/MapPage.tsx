import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useCallback, useMemo } from "react";
import { Link, useSearchParams } from "react-router";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { QueryState } from "../components/QueryState";
import { SearchBox } from "../components/SearchBox";
import { CardView } from "../features/card/CardView";
import { useCard } from "../features/card/useCard";
import { cardLink, searchResultParams } from "../features/map/mapLink";
import { MapPanel } from "../features/map/MapPanel";
import {
  parseMapUrl,
  serializeMapUrl,
  type Overlay,
  type RiskLayer,
} from "../features/map/urlState";
import hr from "../i18n/hr.json";
import { ApiError, fetchStations, type GeocodeResult } from "../lib/api/client";
import { useSources } from "../lib/api/hooks";

// The map library is large, so the search and the panel appear before it has loaded.
const MapView = lazy(() =>
  import("../features/map/MapView").then((module) => ({
    default: module.MapView,
  })),
);

// The basemap style brings its own OpenStreetMap attribution.
const ATTRIBUTION_SOURCES = [
  "dgu_au",
  "dzs_naselja_2021",
  "estat_census_grid_2021",
];

function currentState() {
  return parseMapUrl(new URLSearchParams(window.location.search));
}

function cardError(error: unknown): string {
  return error instanceof ApiError && error.status === 404
    ? hr.card.outside
    : hr.card.error;
}

export function MapPage() {
  const [params, setParams] = useSearchParams();
  const state = useMemo(() => parseMapUrl(params), [params]);
  const { data: sources } = useSources();
  const stationsQuery = useQuery({
    queryKey: ["stations"],
    queryFn: ({ signal }) => fetchStations(signal),
    enabled: state.overlays.includes("stations"),
    staleTime: 5 * 60 * 1000,
  });
  const card = useCard(
    state.pin?.lat ?? null,
    state.pin?.lon ?? null,
    state.label,
    state.scope,
  );

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
      // The URL is read directly, so a late moveend cannot undo a change not yet rendered.
      if (!window.location.pathname.startsWith("/karta")) return;
      setParams(serializeMapUrl({ ...currentState(), view, bbox: null }), {
        replace: true,
      });
    },
    [setParams],
  );

  const onPick = useCallback(
    (point: { lat: number; lon: number }) => {
      setParams(
        serializeMapUrl({
          ...currentState(),
          pin: point,
          label: null,
          scope: "point",
        }),
      );
    },
    [setParams],
  );

  function onLayer(layer: RiskLayer) {
    setParams(serializeMapUrl({ ...currentState(), layer }), { replace: true });
  }

  function onToggleOverlay(overlay: Overlay) {
    const current = currentState();
    const overlays = current.overlays.includes(overlay)
      ? current.overlays.filter((item) => item !== overlay)
      : [...current.overlays, overlay];
    setParams(serializeMapUrl({ ...current, overlays }), { replace: true });
  }

  function onSearch(result: GeocodeResult) {
    setParams(searchResultParams(result, params));
  }

  function closeCard() {
    setParams(
      serializeMapUrl({
        ...currentState(),
        pin: null,
        label: null,
        scope: "point",
      }),
    );
  }

  return (
    <div className="absolute inset-0">
      <h1 className="sr-only">{hr.map.label}</h1>
      <ErrorBoundary message={hr.map.unavailable}>
        <Suspense fallback={null}>
          <MapView
            layer={state.layer}
            overlays={state.overlays}
            view={state.view}
            bbox={state.bbox}
            pin={state.pin}
            attribution={attribution}
            stations={stationsQuery.data}
            onViewChange={onViewChange}
            onPick={onPick}
          />
        </Suspense>
      </ErrorBoundary>
      <div className="pointer-events-none absolute inset-x-3 top-3 z-20 flex justify-end">
        <div className="pointer-events-auto w-full max-w-sm max-md:mt-11">
          <SearchBox onSelect={onSearch} />
        </div>
      </div>
      <MapPanel
        layer={state.layer}
        overlays={state.overlays}
        onLayer={onLayer}
        onToggleOverlay={onToggleOverlay}
      />
      {state.pin && (
        <aside
          aria-label={hr.card.title}
          className="absolute inset-x-0 bottom-0 z-30 max-h-[65%] overflow-y-auto rounded-t-xl bg-white p-4 shadow-2xl md:inset-x-auto md:top-16 md:right-3 md:bottom-3 md:max-h-none md:w-[26rem] md:rounded-xl"
          data-testid="card-panel"
        >
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <Link
              to={cardLink(
                state.pin.lat,
                state.pin.lon,
                state.label,
                state.scope,
              )}
              className="text-sm underline"
            >
              {hr.map.fullCard}
            </Link>
            <button
              type="button"
              onClick={closeCard}
              className="text-sm underline"
            >
              {hr.map.closeCard}
            </button>
          </div>
          <QueryState query={card} loading={hr.card.loading} error={cardError}>
            {(data) => <CardView card={data} compact />}
          </QueryState>
        </aside>
      )}
    </div>
  );
}
