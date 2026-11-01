import { useState } from "react";
import hr from "../../i18n/hr.json";
import type { CardResponse } from "../../lib/api/client";
import { formatNumber } from "../../lib/format/number";
import { HAZARD_NAMES, weightedRisk, type HazardName } from "./weights";

const DEFAULT = { flood: 25, heat: 25, fire: 25, air: 25 };

/** Recalculated from the card's R values in the browser (SPEC §5.5); nothing is sent anywhere. */
export function WeightSliders({
  hazards,
}: {
  hazards: CardResponse["hazards"];
}) {
  const [weights, setWeights] = useState<Record<HazardName, number>>(DEFAULT);
  const risks = {
    flood: hazards.flood.r,
    heat: hazards.heat.r,
    fire: hazards.fire.r,
    air: hazards.air.r,
  };
  const value = weightedRisk(risks, weights);
  return (
    <details className="mt-3 print:hidden">
      <summary className="cursor-pointer font-medium">
        {hr.card.weightsTitle}
      </summary>
      <p className="mt-1 text-sm text-slate-700">{hr.card.weightsHelp}</p>
      <div className="mt-2 space-y-2">
        {HAZARD_NAMES.map((name) => (
          <label key={name} className="flex items-center gap-2 text-sm">
            <span className="w-20">{hr.card.hazards[name]}</span>
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={weights[name]}
              onChange={(event) =>
                setWeights({ ...weights, [name]: Number(event.target.value) })
              }
              className="min-w-0 flex-1"
            />
            <span className="w-8 text-right">{weights[name]}</span>
          </label>
        ))}
      </div>
      <p className="mt-2 text-sm">
        {hr.card.weightedValue}{" "}
        <strong>{value === null ? "–" : formatNumber(value, 3)}</strong>{" "}
        <button
          type="button"
          className="ml-2 underline"
          onClick={() => setWeights(DEFAULT)}
        >
          {hr.card.weightsReset}
        </button>
      </p>
    </details>
  );
}
