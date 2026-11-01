import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { LevelBadge } from "../../components/LevelBadge";
import { QueryState } from "../../components/QueryState";
import hr from "../../i18n/hr.json";
import { fetchRankings } from "../../lib/api/client";
import { HV_VIEWER, RISK_SPECS } from "./layers";
import {
  OVERLAYS,
  RISK_LAYERS,
  type Overlay,
  type RiskLayer,
} from "./urlState";

interface Props {
  layer: RiskLayer;
  overlays: Overlay[];
  onLayer: (layer: RiskLayer) => void;
  onToggleOverlay: (overlay: Overlay) => void;
}

const TABLE_SIZE = 20;

function TableView() {
  const query = useQuery({
    queryKey: ["rankings", TABLE_SIZE],
    queryFn: ({ signal }) => fetchRankings(TABLE_SIZE, signal),
  });
  return (
    <QueryState query={query}>
      {(rows) => (
        <div>
          <h2 className="font-semibold">{hr.map.tableTitle}</h2>
          <ol className="mt-1 space-y-1">
            {rows.map((row) => (
              <li
                key={row.code}
                className="flex items-center justify-between gap-2"
              >
                <Link to={`/opcine/${row.code}`} className="underline">
                  {row.rank_hr}. {row.name}
                </Link>
                <LevelBadge level={row.ikr_class} compact />
              </li>
            ))}
          </ol>
          <Link to="/opcine" className="mt-2 block underline">
            {hr.map.tableAll}
          </Link>
        </div>
      )}
    </QueryState>
  );
}

export function MapPanel({ layer, overlays, onLayer, onToggleOverlay }: Props) {
  const [table, setTable] = useState(false);
  return (
    <details
      open={window.matchMedia?.("(min-width: 768px)").matches ?? true}
      className="absolute top-3 left-3 z-10 max-h-[calc(100%-5rem)] w-[min(calc(100%-1.5rem),20rem)] overflow-y-auto rounded-lg bg-white text-sm text-slate-900 shadow-lg"
    >
      <summary className="cursor-pointer rounded-lg px-3 py-2 font-semibold focus-visible:outline-2 focus-visible:outline-slate-900">
        {hr.map.panelTitle}
      </summary>
      <div className="space-y-3 px-3 pb-3">
        <p className="text-slate-700">{hr.map.clickHint}</p>
        <fieldset>
          <legend className="font-semibold">{hr.map.layerGroup}</legend>
          {RISK_LAYERS.map((item) => (
            <label key={item} className="mt-1 flex items-center gap-2">
              <input
                type="radio"
                name="risk-layer"
                checked={layer === item}
                onChange={() => onLayer(item)}
              />
              {hr.map.layers[item]}
            </label>
          ))}
        </fieldset>
        <div>
          <h2 className="font-semibold">{hr.map.legend[layer]}</h2>
          <ul className="mt-1 space-y-0.5">
            {RISK_SPECS[layer].legend.map((step) => (
              <li key={step.label} className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className="inline-block h-3 w-5 border border-slate-400"
                  style={{ backgroundColor: step.color }}
                />
                {step.label}
              </li>
            ))}
          </ul>
          <p className="mt-1 text-slate-700">{hr.map.zoomHint}</p>
        </div>
        <fieldset>
          <legend className="font-semibold">{hr.map.overlayGroup}</legend>
          {OVERLAYS.map((item) => (
            <label key={item} className="mt-1 flex items-center gap-2">
              <input
                type="checkbox"
                checked={overlays.includes(item)}
                onChange={() => onToggleOverlay(item)}
              />
              {hr.map.overlays[item]}
            </label>
          ))}
        </fieldset>
        {overlays.includes("hv") && (
          <p className="text-xs text-slate-700">
            {hr.map.hvNote}{" "}
            <a
              href={HV_VIEWER}
              className="underline"
              target="_blank"
              rel="noreferrer"
            >
              {hr.map.hvLink}
            </a>
          </p>
        )}
        <label className="flex items-center gap-2 font-semibold">
          <input
            type="checkbox"
            checked={table}
            onChange={() => setTable(!table)}
          />
          {hr.map.tableToggle}
        </label>
        {table && <TableView />}
        <p className="text-xs text-slate-700">{hr.app.disclaimer}</p>
      </div>
    </details>
  );
}
