import { useQuery } from "@tanstack/react-query";
import { fetchSources } from "../../lib/api/client";

export function useSources() {
  return useQuery({
    queryKey: ["sources"],
    queryFn: ({ signal }) => fetchSources(signal),
    staleTime: 5 * 60 * 1000,
  });
}
