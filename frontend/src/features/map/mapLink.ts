import type { GeocodeResult } from "../../lib/api/client";
import { parseMapUrl, serializeMapUrl } from "./urlState";

/** Map URL state for a search result: the area fits the view and the point opens its card. */
export function searchResultParams(
  result: GeocodeResult,
  current: URLSearchParams,
): URLSearchParams {
  return serializeMapUrl({
    ...parseMapUrl(current),
    view: null,
    bbox: result.bbox ? [...result.bbox] : null,
    pin: { lat: result.lat, lon: result.lon },
    label: result.label,
  });
}

export function cardLink(
  lat: number,
  lon: number,
  label: string | null,
): string {
  const params = new URLSearchParams({ lat: String(lat), lon: String(lon) });
  if (label) params.set("naziv", label);
  return `/iskaznica?${params}`;
}
