import type { components } from "./schema";

type Schemas = components["schemas"];
export type GeocodeResponse = Schemas["GeocodeResponse"];
export type GeocodeResult = Schemas["GeocodeResult"];
export type SourceInfo = Schemas["SourceInfo"];
export type CardResponse = Schemas["CardResponse"];
export type HazardBlock = Schemas["HazardBlock"];
export type WarningItem = Schemas["Warning"];
export type WarningsResponse = Schemas["WarningsResponse"];
export type AirStation = Schemas["AirStation"];
export type JlsListItem = Schemas["JlsListItem"];
export type JlsDetail = Schemas["JlsDetail"];
export type JlsNaselje = Schemas["JlsNaselje"];
export type JlsCell = Schemas["JlsCell"];
export type RankingItem = Schemas["RankingItem"];
export type LiveStatus = Schemas["LiveStatus"];
export type AreaSummary = Schemas["AreaSummary"];

export type QuickAnswer = Schemas["QuickAnswer"];
export type Citation = Schemas["Citation"];
export type AgentStatus = Schemas["AgentStatus"];
export type QualityRow = Schemas["QualityRow"];
export type ExportFile = Schemas["ExportFile"];
export type QuickId =
  "older_exposed" | "hottest" | "air_near" | "warnings" | "flood_data";

const API = "/api/v1";

export class ApiError extends Error {
  constructor(readonly status: number) {
    super(`HTTP ${status}`);
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API}${path}`, { signal });
  if (!response.ok) {
    throw new ApiError(response.status);
  }
  return (await response.json()) as T;
}

export interface GeocodeOptions {
  kinds?: GeocodeResult["kind"][];
  jls?: string;
}

export function fetchGeocode(
  query: string,
  signal?: AbortSignal,
  options: GeocodeOptions = {},
): Promise<GeocodeResponse> {
  const params = new URLSearchParams({ q: query });
  for (const kind of options.kinds ?? []) params.append("kinds", kind);
  if (options.jls) params.set("jls", options.jls);
  return getJson(`/geocode?${params}`, signal);
}

export function fetchSources(signal?: AbortSignal): Promise<SourceInfo[]> {
  return getJson("/sources", signal);
}

export type CardScope = "point" | "naselje" | "jls";

export function fetchCard(
  lat: number,
  lon: number,
  label: string | null,
  scope: CardScope,
  signal?: AbortSignal,
): Promise<CardResponse> {
  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
    scope,
  });
  if (label) params.set("label", label);
  return getJson(`/card?${params}`, signal);
}

export function fetchWarnings(signal?: AbortSignal): Promise<WarningsResponse> {
  return getJson("/warnings/active", signal);
}

export function fetchStations(signal?: AbortSignal): Promise<AirStation[]> {
  return getJson("/air/stations", signal);
}

export function fetchJlsList(signal?: AbortSignal): Promise<JlsListItem[]> {
  return getJson("/jls", signal);
}

export function fetchJls(
  code: string,
  signal?: AbortSignal,
): Promise<JlsDetail> {
  return getJson(`/jls/${encodeURIComponent(code)}`, signal);
}

export function fetchJlsNaselja(
  code: string,
  signal?: AbortSignal,
): Promise<JlsNaselje[]> {
  return getJson(`/jls/${encodeURIComponent(code)}/naselja`, signal);
}

export function fetchJlsCells(
  code: string,
  signal?: AbortSignal,
): Promise<JlsCell[]> {
  return getJson(`/jls/${encodeURIComponent(code)}/cells`, signal);
}

export function fetchRankings(
  limit: number,
  signal?: AbortSignal,
): Promise<RankingItem[]> {
  return getJson(`/rankings?limit=${limit}`, signal);
}

export function fetchAgentStatus(signal?: AbortSignal): Promise<AgentStatus> {
  return getJson("/agent/status", signal);
}

export function fetchQuick(
  question: QuickId,
  options: { jls?: string; lat?: number; lon?: number },
  signal?: AbortSignal,
): Promise<QuickAnswer> {
  const params = new URLSearchParams({ question });
  if (options.jls) params.set("jls", options.jls);
  if (options.lat !== undefined) params.set("lat", String(options.lat));
  if (options.lon !== undefined) params.set("lon", String(options.lon));
  return getJson(`/agent/quick?${params}`, signal);
}

export function fetchQuality(signal?: AbortSignal): Promise<QualityRow[]> {
  return getJson("/quality", signal);
}

export function fetchExports(signal?: AbortSignal): Promise<ExportFile[]> {
  return getJson("/exports", signal);
}

export interface ChatAnswer {
  text: string;
  citations: Citation[];
  map_actions: { type: string; lat: number; lon: number; label: string }[];
  grounded: boolean;
}

/** Reads the server-sent events of one question; nothing about it is stored. */
export async function streamChat(
  message: string,
  onTool: (name: string) => void,
  signal?: AbortSignal,
): Promise<ChatAnswer | null> {
  const response = await fetch(`${API}/agent/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
    signal,
  });
  if (!response.ok || !response.body) throw new ApiError(response.status);
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  let answer: ChatAnswer | null = null;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return answer;
    buffer += value;
    let end = buffer.indexOf("\n\n");
    while (end >= 0) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const event = /^event: (.*)$/m.exec(block)?.[1];
      const data = /^data: (.*)$/m.exec(block)?.[1];
      if (event === "tool" && data)
        onTool((JSON.parse(data) as { name: string }).name);
      if (event === "answer" && data) answer = JSON.parse(data) as ChatAnswer;
      end = buffer.indexOf("\n\n");
    }
  }
}
