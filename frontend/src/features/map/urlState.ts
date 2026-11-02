export type RiskLayer =
  "ikr" | "flood" | "heat" | "fire" | "air" | "pop65" | "population";
export type Overlay = "jls" | "stations" | "nature" | "hv";

export const RISK_LAYERS: readonly RiskLayer[] = [
  "ikr",
  "flood",
  "heat",
  "fire",
  "air",
  "pop65",
  "population",
];
export const OVERLAYS: readonly Overlay[] = ["jls", "stations", "nature", "hv"];
const DEFAULT_OVERLAYS: readonly Overlay[] = ["jls"];

const SCOPES = ["point", "naselje", "jls"] as const;

export type Bbox = [west: number, south: number, east: number, north: number];

export interface MapUrlState {
  layer: RiskLayer;
  overlays: Overlay[];
  view: { lat: number; lon: number; zoom: number } | null;
  bbox: Bbox | null;
  pin: { lat: number; lon: number } | null;
  label: string | null;
  scope: "point" | "naselje" | "jls";
}

function numbers(value: string | null, count: number): number[] | null {
  if (!value) return null;
  const parsed = value.split(",").map(Number);
  return parsed.length === count && parsed.every(Number.isFinite)
    ? parsed
    : null;
}

export function parseMapUrl(params: URLSearchParams): MapUrlState {
  const layerParam = params.get("sloj") as RiskLayer | null;
  const overlayParam = params.get("slojevi");
  const view = numbers(params.get("pogled"), 3);
  const bbox = numbers(params.get("okvir"), 4);
  const pin = numbers(params.get("oznaka"), 2);
  return {
    layer: layerParam && RISK_LAYERS.includes(layerParam) ? layerParam : "ikr",
    overlays:
      overlayParam === null
        ? [...DEFAULT_OVERLAYS]
        : OVERLAYS.filter((item) => overlayParam.split(",").includes(item)),
    view: view && { lat: view[0], lon: view[1], zoom: view[2] },
    bbox: bbox && (bbox as Bbox),
    pin: pin && { lat: pin[0], lon: pin[1] },
    label: params.get("naziv"),
    scope: SCOPES.find((item) => item === params.get("razina")) ?? "point",
  };
}

export function serializeMapUrl(state: MapUrlState): URLSearchParams {
  const params = new URLSearchParams();
  if (state.layer !== "ikr") params.set("sloj", state.layer);
  const isDefault =
    state.overlays.length === DEFAULT_OVERLAYS.length &&
    state.overlays.every((item) => DEFAULT_OVERLAYS.includes(item));
  if (!isDefault) params.set("slojevi", state.overlays.join(","));
  if (state.view) {
    const { lat, lon, zoom } = state.view;
    params.set(
      "pogled",
      `${lat.toFixed(5)},${lon.toFixed(5)},${zoom.toFixed(2)}`,
    );
  }
  if (state.bbox) params.set("okvir", state.bbox.join(","));
  if (state.pin)
    params.set(
      "oznaka",
      `${state.pin.lat.toFixed(6)},${state.pin.lon.toFixed(6)}`,
    );
  if (state.label) params.set("naziv", state.label);
  if (state.scope !== "point") params.set("razina", state.scope);
  return params;
}
