export const HAZARD_NAMES = ["flood", "heat", "fire", "air"] as const;
export type HazardName = (typeof HAZARD_NAMES)[number];

/** Weighted mean of the hazards that have a value, as in the server-side index. */
export function weightedRisk(
  risks: Record<HazardName, number | null | undefined>,
  weights: Record<HazardName, number>,
): number | null {
  let total = 0;
  let weightSum = 0;
  for (const name of HAZARD_NAMES) {
    const risk = risks[name];
    if (risk != null) {
      total += risk * weights[name];
      weightSum += weights[name];
    }
  }
  return weightSum > 0 ? total / weightSum : null;
}
