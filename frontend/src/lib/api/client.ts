import type { components } from "./schema";

export type GeocodeResponse = components["schemas"]["GeocodeResponse"];
export type GeocodeResult = components["schemas"]["GeocodeResult"];
export type SourceInfo = components["schemas"]["SourceInfo"];

const API = "/api/v1";

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API}${path}`, { signal });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetchGeocode(
  query: string,
  signal?: AbortSignal,
): Promise<GeocodeResponse> {
  return getJson(`/geocode?${new URLSearchParams({ q: query })}`, signal);
}

export function fetchSources(signal?: AbortSignal): Promise<SourceInfo[]> {
  return getJson("/sources", signal);
}
