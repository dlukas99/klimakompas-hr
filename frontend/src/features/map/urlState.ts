export type LayerId = "jls" | "stanovnistvo";

export const ALL_LAYERS: readonly LayerId[] = ["jls", "stanovnistvo"];

export type Bbox = [west: number, south: number, east: number, north: number];

export interface MapUrlState {
  layers: LayerId[];
  view: { lat: number; lon: number; zoom: number } | null;
  bbox: Bbox | null;
  pin: { lat: number; lon: number } | null;
}

function numbers(value: string | null, count: number): number[] | null {
  if (!value) return null;
  const parsed = value.split(",").map(Number);
  return parsed.length === count && parsed.every(Number.isFinite)
    ? parsed
    : null;
}

export function parseMapUrl(params: URLSearchParams): MapUrlState {
  const layerParam = params.get("slojevi");
  const layers =
    layerParam === null
      ? [...ALL_LAYERS]
      : ALL_LAYERS.filter((layer) => layerParam.split(",").includes(layer));
  const view = numbers(params.get("pogled"), 3);
  const bbox = numbers(params.get("okvir"), 4);
  const pin = numbers(params.get("oznaka"), 2);
  return {
    layers,
    view: view && { lat: view[0], lon: view[1], zoom: view[2] },
    bbox: bbox && (bbox as Bbox),
    pin: pin && { lat: pin[0], lon: pin[1] },
  };
}

export function serializeMapUrl(state: MapUrlState): URLSearchParams {
  const params = new URLSearchParams();
  if (state.layers.length !== ALL_LAYERS.length) {
    params.set("slojevi", state.layers.join(","));
  }
  if (state.view) {
    const { lat, lon, zoom } = state.view;
    params.set(
      "pogled",
      `${lat.toFixed(5)},${lon.toFixed(5)},${zoom.toFixed(2)}`,
    );
  }
  if (state.bbox) params.set("okvir", state.bbox.join(","));
  if (state.pin) params.set("oznaka", `${state.pin.lat},${state.pin.lon}`);
  return params;
}
