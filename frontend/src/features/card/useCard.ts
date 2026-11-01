import { useQuery } from "@tanstack/react-query";
import { fetchCard } from "../../lib/api/client";

export function useCard(
  lat: number | null,
  lon: number | null,
  label: string | null,
) {
  return useQuery({
    queryKey: ["card", lat, lon, label],
    queryFn: ({ signal }) =>
      fetchCard(lat as number, lon as number, label, signal),
    enabled: lat !== null && lon !== null,
    retry: false,
  });
}
