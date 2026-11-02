import type { CardScope, GeocodeResult } from "../../lib/api/client";
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
    scope: scopeOf(result),
  });
}

/** A searched settlement or JLS is shown as an area; an address or a map click as a point. */
export function scopeOf(result: GeocodeResult): CardScope {
  if (result.kind === "settlement") return "naselje";
  if (result.kind === "municipality") return "jls";
  return "point";
}

export function cardLink(
  lat: number,
  lon: number,
  label: string | null,
  scope: CardScope = "point",
): string {
  const params = new URLSearchParams({ lat: String(lat), lon: String(lon) });
  if (label) params.set("naziv", label);
  if (scope !== "point") params.set("razina", scope);
  return `/iskaznica?${params}`;
}
