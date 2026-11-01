import type { GeocodeResult } from "../../lib/api/client";
import { parseMapUrl, serializeMapUrl } from "./urlState";

/** Map URL state for a search result: areas fit their bounding box, addresses get a pin. */
export function searchResultParams(
  result: GeocodeResult,
  current: URLSearchParams,
): URLSearchParams {
  const state = parseMapUrl(current);
  return serializeMapUrl({
    ...state,
    view: null,
    bbox: result.bbox ? [...result.bbox] : null,
    pin: result.bbox ? null : { lat: result.lat, lon: result.lon },
  });
}
