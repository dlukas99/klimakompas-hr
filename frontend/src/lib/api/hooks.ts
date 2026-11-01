import { useQuery } from "@tanstack/react-query";
import { fetchSources, fetchWarnings } from "./client";

const FIVE_MINUTES = 5 * 60 * 1000;

export function useSources() {
  return useQuery({
    queryKey: ["sources"],
    queryFn: ({ signal }) => fetchSources(signal),
    staleTime: FIVE_MINUTES,
  });
}

export function useWarnings() {
  return useQuery({
    queryKey: ["warnings"],
    queryFn: ({ signal }) => fetchWarnings(signal),
    staleTime: FIVE_MINUTES,
    refetchInterval: FIVE_MINUTES,
  });
}
