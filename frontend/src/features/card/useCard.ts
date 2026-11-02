import { useQuery } from "@tanstack/react-query";
import { fetchCard, type CardScope } from "../../lib/api/client";

export function useCard(
  lat: number | null,
  lon: number | null,
  label: string | null,
  scope: CardScope = "point",
) {
  return useQuery({
    queryKey: ["card", lat, lon, label, scope],
    queryFn: ({ signal }) =>
      fetchCard(lat as number, lon as number, label, scope, signal),
    enabled: lat !== null && lon !== null,
    retry: false,
  });
}
