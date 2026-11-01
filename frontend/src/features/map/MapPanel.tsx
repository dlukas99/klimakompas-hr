import hr from "../../i18n/hr.json";
import { formatDateTime } from "../../lib/format/date";
import { formatNumber } from "../../lib/format/number";
import { POPULATION_CLASSES } from "./layers";
import type { MapSelection } from "./MapView";
import type { LayerId } from "./urlState";
import { useSources } from "./useSources";

const MAP_SOURCES = ["dgu_au", "dzs_naselja_2021", "estat_census_grid_2021"];

interface Props {
  layers: LayerId[];
  onToggle: (layer: LayerId) => void;
  selection: MapSelection[];
  onClearSelection: () => void;
}

function classLabel(index: number): string {
  const from = POPULATION_CLASSES[index].from;
  const next = POPULATION_CLASSES[index + 1]?.from;
  return next === undefined
    ? `${formatNumber(from)} i više`
    : `${formatNumber(from)} – ${formatNumber(next - 1)}`;
}

function Sources() {
  const { data, isPending, isError } = useSources();
  if (isPending) return <p>{hr.map.sourcesLoading}</p>;
  if (isError) return <p>{hr.map.sourcesError}</p>;
  return (
    <ul className="space-y-1">
      {data
        .filter((source) => MAP_SOURCES.includes(source.id))
        .map((source) => (
          <li key={source.id}>
            {source.attribution}
            {source.last_success_at &&
              ` (${hr.map.refreshed} ${formatDateTime(source.last_success_at)})`}
          </li>
        ))}
    </ul>
  );
}

function SelectionDetails({
  selection,
  onClear,
}: {
  selection: MapSelection[];
  onClear: () => void;
}) {
  const jls = selection.find((item) => item.kind === "jls")?.properties;
  const cell = selection.find((item) => item.kind === "cell")?.properties;
  return (
    <section
      aria-label={hr.info.title}
      className="border-b border-slate-200 pb-3"
    >
      <div className="flex items-start justify-between gap-2">
        <h2 className="font-semibold">{hr.info.title}</h2>
        <button
          type="button"
          onClick={onClear}
          className="rounded px-2 py-0.5 text-sm underline focus-visible:outline-2 focus-visible:outline-slate-900"
        >
          {hr.info.close}
        </button>
      </div>
      {jls && (
        <p className="mt-1">
          {jls.kind === "grad" ? hr.info.grad : hr.info.opcina}{" "}
          <strong>{String(jls.name)}</strong>
          <br />
          {hr.info.population}: {formatNumber(Number(jls.pop_total))}
        </p>
      )}
      {cell && (
        <p className="mt-1">
          {hr.info.cellPopulation}: {formatNumber(Number(cell.pop_total))}
        </p>
      )}
    </section>
  );
}

export function MapPanel({
  layers,
  onToggle,
  selection,
  onClearSelection,
}: Props) {
  return (
    <details
      open={window.matchMedia?.("(min-width: 768px)").matches ?? true}
      className="absolute top-3 left-3 z-10 max-h-[calc(100%-5rem)] w-[min(calc(100%-1.5rem),20rem)] overflow-y-auto rounded-lg bg-white text-sm text-slate-900 shadow-lg"
    >
      <summary className="cursor-pointer rounded-lg px-3 py-2 font-semibold focus-visible:outline-2 focus-visible:outline-slate-900">
        {hr.map.panelTitle}
      </summary>
      <div className="space-y-3 px-3 pb-3">
        {selection.length > 0 ? (
          <SelectionDetails selection={selection} onClear={onClearSelection} />
        ) : (
          <p className="text-slate-700">{hr.map.clickHint}</p>
        )}
        <fieldset>
          <legend className="font-semibold">{hr.map.layers}</legend>
          <label className="mt-1 flex items-center gap-2">
            <input
              type="checkbox"
              checked={layers.includes("jls")}
              onChange={() => onToggle("jls")}
            />
            {hr.map.layerJls}
          </label>
          <label className="mt-1 flex items-center gap-2">
            <input
              type="checkbox"
              checked={layers.includes("stanovnistvo")}
              onChange={() => onToggle("stanovnistvo")}
            />
            {hr.map.layerPopulation}
          </label>
        </fieldset>
        {layers.includes("stanovnistvo") && (
          <div>
            <h2 className="font-semibold">{hr.map.legendPopulation}</h2>
            <ul className="mt-1 space-y-0.5">
              {POPULATION_CLASSES.map((item, index) => (
                <li key={item.from} className="flex items-center gap-2">
                  <span
                    aria-hidden="true"
                    className="inline-block h-3 w-5 border border-slate-400"
                    style={{ backgroundColor: item.color }}
                  />
                  {classLabel(index)}
                </li>
              ))}
            </ul>
            <p className="mt-1 text-slate-700">{hr.map.zoomHint}</p>
          </div>
        )}
        <div>
          <h2 className="font-semibold">{hr.map.sources}</h2>
          <Sources />
        </div>
        <p className="text-xs text-slate-700">{hr.app.disclaimer}</p>
      </div>
    </details>
  );
}
