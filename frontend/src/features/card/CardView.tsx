import { useState, type ReactNode } from "react";
import { Link } from "react-router";
import { LevelBadge } from "../../components/LevelBadge";
import hr from "../../i18n/hr.json";
import type {
  CardResponse,
  HazardBlock,
  WarningItem,
} from "../../lib/api/client";
import { useSources } from "../../lib/api/hooks";
import { formatAgo, formatDate, formatDateTime } from "../../lib/format/date";
import { formatNumber } from "../../lib/format/number";
import { fill } from "../../lib/format/template";
import { EAQI_COLORS, EAQI_TEXT } from "../map/layers";
import { HAZARD_NAMES, type HazardName } from "./weights";
import { WeightSliders } from "./WeightSliders";

const POLLUTANT_LABELS: Record<string, string> = {
  pm25: "PM2,5",
  pm10: "PM10",
  no2: "NO₂",
  o3: "O₃",
};
const ADVICE_BY_HAZARD: Record<HazardName, string> = {
  flood: "poplave",
  heat: "toplina",
  fire: "pozar",
  air: "zrak",
};

function percent(value: number | null | undefined): string {
  return value == null
    ? hr.card.shareUnavailable
    : formatNumber(value * 100, 0);
}

function num(value: unknown, digits = 0): string {
  return typeof value === "number" ? formatNumber(value, digits) : "–";
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-t border-slate-200 py-3">
      <h2 className="mb-1 font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function WarningRow({ warning }: { warning: WarningItem }) {
  return (
    <li className="rounded border border-amber-300 bg-amber-50 p-2 text-sm">
      <p className="font-medium">{warning.event}</p>
      {warning.onset && warning.expires && (
        <p className="text-slate-800">
          {hr.card.warningFrom} {formatDateTime(warning.onset)}{" "}
          {hr.card.warningTo} {formatDateTime(warning.expires)}
        </p>
      )}
      {warning.description && <p>{warning.description}</p>}
      {warning.instruction && (
        <p className="text-slate-800">{warning.instruction}</p>
      )}
    </li>
  );
}

function hazardLines(name: HazardName, card: CardResponse): string[] {
  const key = card.hazards[name].key_value;
  const lines: string[] = [];
  if (name === "flood") {
    if (key.zone_return_period) {
      lines.push(
        fill(hr.card.flood.zone, { rp: Number(key.zone_return_period) }),
      );
    } else if (key.near_rp100) {
      lines.push(hr.card.flood.near);
    } else {
      lines.push(hr.card.flood.none);
    }
    if (typeof key.depth_rp100_m === "number" && key.depth_rp100_m > 0) {
      lines.push(
        fill(hr.card.flood.depth, {
          value: formatNumber(key.depth_rp100_m, 1),
        }),
      );
    }
    lines.push(hr.card.flood.limit, hr.card.flood.official);
  }
  if (name === "heat") {
    lines.push(fill(hr.card.heat.hotDays, { value: num(key.hot_days) }));
    lines.push(fill(hr.card.heat.nights, { value: num(key.tropical_nights) }));
    if (typeof key.lst_delta_c === "number") {
      const template =
        key.lst_delta_c >= 0 ? hr.card.heat.delta : hr.card.heat.cooler;
      lines.push(
        fill(template, { value: formatNumber(Math.abs(key.lst_delta_c), 1) }),
      );
    }
    if (typeof key.tree_share === "number") {
      lines.push(
        fill(hr.card.heat.trees, {
          value: formatNumber(key.tree_share * 100, 0),
        }),
      );
    }
  }
  if (name === "fire") {
    lines.push(fill(hr.card.fire.days, { value: num(key.fwi_days) }));
    if (typeof key.fuel_share === "number") {
      lines.push(
        fill(hr.card.fire.fuel, {
          value: formatNumber(key.fuel_share * 100, 0),
        }),
      );
    }
    lines.push(fill(hr.card.fire.burnt, { value: num(key.burnt_years_2km) }));
    const index = card.live.fire_index;
    if (index) {
      lines.push(
        fill(index.in_season ? hr.card.fire.index : hr.card.fire.indexOff, {
          station: index.station_name ?? "",
          category: index.category ?? "",
          fwi: num(index.fwi),
        }),
      );
    }
  }
  if (name === "air") {
    lines.push(
      fill(hr.card.air.annual, {
        year: Number(key.year),
        value: num(key.pm25_annual, 1),
        who: Number(key.who_guideline),
      }),
    );
  }
  return lines;
}

function AirNowBlock({ card }: { card: CardResponse }) {
  const air = card.live.air_now;
  if (!air) return <p className="mt-1 text-sm">{hr.card.air.nowNone}</p>;
  const values = {
    station: air.station.name,
    distance: formatNumber(air.station.distance_km, 1),
  };
  const note =
    air.substitution === "local_pm10"
      ? fill(hr.card.air.nowSubLocalPm10, values)
      : air.substitution === "nearest_pm25"
        ? fill(hr.card.air.nowSubNearest, values)
        : fill(hr.card.air.now, values);
  return (
    <div className="mt-2 text-sm">
      <p className="font-medium">{note}</p>
      <ul className="mt-1 flex flex-wrap gap-1">
        {Object.entries(air.values)
          .filter(([, value]) => !value.stale)
          .map(([pollutant, value]) => (
            <li
              key={pollutant}
              className="rounded px-2 py-0.5"
              style={{
                backgroundColor: EAQI_COLORS[value.eaqi_class - 1],
                color: EAQI_TEXT[value.eaqi_class - 1],
              }}
            >
              {POLLUTANT_LABELS[pollutant]}: {formatNumber(value.value, 1)}{" "}
              {value.unit ?? ""} · {value.eaqi_label}
            </li>
          ))}
      </ul>
      <p className="mt-1 text-slate-700">
        {fill(hr.card.air.measured, { time: formatAgo(air.observed_at) })}
      </p>
      {card.live.air_forecast.length > 0 ? (
        <div className="mt-2">
          <p className="font-medium">{hr.card.air.forecast}</p>
          <ul>
            {card.live.air_forecast.map((point) => (
              <li key={point.target_time}>
                {formatDateTime(point.target_time)}:{" "}
                {formatNumber(point.pm25, 1)} µg/m³
                {point.lo != null && point.hi != null
                  ? ` (${formatNumber(point.lo, 1)} – ${formatNumber(point.hi, 1)})`
                  : ""}
              </li>
            ))}
          </ul>
          <p className="text-slate-700">
            {fill(hr.card.air.forecastModel, {
              model: card.live.air_forecast[0].model_version,
            })}
          </p>
        </div>
      ) : (
        <p className="mt-1 text-slate-700">{hr.card.air.forecastNone}</p>
      )}
    </div>
  );
}

function SourceNames({ ids }: { ids: string[] }) {
  const { data } = useSources();
  if (!data) return <>{ids.join(", ")}</>;
  return (
    <>
      {ids
        .map((id) => data.find((source) => source.id === id))
        .filter((source) => source !== undefined)
        .map((source) =>
          source.last_success_at
            ? `${source.attribution} (${formatDate(source.last_success_at.slice(0, 10))})`
            : source.attribution,
        )
        .join(" · ")}
    </>
  );
}

function HazardCard({ name, card }: { name: HazardName; card: CardResponse }) {
  const block: HazardBlock = card.hazards[name];
  return (
    <article
      className="rounded-lg border border-slate-200 p-3"
      data-testid={`hazard-${name}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold">{hr.card.hazards[name]}</h3>
        <LevelBadge level={block.level} />
      </div>
      <ul className="mt-1 space-y-0.5 text-sm">
        {hazardLines(name, card).map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      {name === "air" && <AirNowBlock card={card} />}
      {block.explanation.length > 0 && (
        <details className="mt-2 text-sm">
          <summary className="cursor-pointer font-medium">
            {hr.card.why}
          </summary>
          <p className="mt-1 text-slate-700">{hr.card.whyHelp}</p>
          <dl className="mt-1 grid grid-cols-[1fr_auto] gap-x-3">
            {block.explanation.map((item) => (
              <div key={item.factor} className="contents">
                <dt>{hr.card.factor[item.factor]}</dt>
                <dd className="text-right">{formatNumber(item.value, 3)}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
      <p className="mt-2 text-xs text-slate-700">
        {hr.card.sourcesTitle}: <SourceNames ids={block.source_ids} />
      </p>
    </article>
  );
}

function Actions({ card }: { card: CardResponse }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex flex-wrap items-center gap-2 print:hidden">
      <button
        type="button"
        onClick={() => window.print()}
        className="rounded border border-slate-400 px-3 py-1 text-sm"
      >
        {hr.card.printAction}
      </button>
      <button
        type="button"
        onClick={() => {
          void navigator.clipboard
            ?.writeText(window.location.href)
            .then(() => setCopied(true));
        }}
        className="rounded border border-slate-400 px-3 py-1 text-sm"
      >
        {hr.card.copyAction}
      </button>
      <Link
        to={`/opcine/${card.location.jls.code}`}
        className="rounded border border-slate-400 px-3 py-1 text-sm"
      >
        {hr.card.jlsAction}
      </Link>
      {copied && (
        <span role="status" className="text-sm">
          {hr.card.copied}
        </span>
      )}
    </div>
  );
}

export function CardView({
  card,
  compact = false,
}: {
  card: CardResponse;
  compact?: boolean;
}) {
  const { location, ikr, population, live } = card;
  const warningsChecked = live.warnings_checked_at;
  return (
    <div className="text-slate-900">
      <header>
        <p className="text-sm text-slate-700">{hr.card.title}</p>
        <h1 className="text-xl font-bold">{location.label}</h1>
        <p className="text-sm text-slate-800">
          {location.naselje.name}, {location.jls.name}, {location.zupanija.name}
        </p>
        <p className="text-xs text-slate-700">
          {hr.card.cell}: {location.cell_id}
        </p>
      </header>

      {card.partial && (
        <p
          role="status"
          className="mt-2 rounded bg-amber-100 p-2 text-sm text-amber-950"
        >
          {hr.card.partial}
        </p>
      )}

      <section className="mt-3 rounded-lg bg-slate-100 p-3">
        <h2 className="font-semibold">{hr.card.ikrTitle}</h2>
        {ikr.populated ? (
          <>
            <div className="mt-1">
              <LevelBadge level={ikr.level} />
            </div>
            {ikr.percentile != null && (
              <p className="mt-1">
                {fill(hr.card.ikrHigherThan, {
                  value: formatNumber(ikr.percentile, 0),
                })}
              </p>
            )}
            <p className="text-sm text-slate-700">{hr.card.ikrRelative}</p>
            <WeightSliders hazards={card.hazards} />
          </>
        ) : (
          <p className="mt-1">{hr.card.ikrUnpopulated}</p>
        )}
      </section>

      <Section title={hr.card.warningsTitle}>
        {warningsChecked == null ? (
          <p className="text-sm">{hr.card.warningsUnknown}</p>
        ) : live.warnings.length === 0 ? (
          <p className="text-sm">
            {hr.card.warningsNone} (
            {fill(hr.card.warningsChecked, {
              time: formatAgo(warningsChecked),
            })}
            )
          </p>
        ) : (
          <>
            <ul className="space-y-1">
              {live.warnings.map((warning) => (
                <WarningRow key={warning.id} warning={warning} />
              ))}
            </ul>
            <p className="mt-1 text-xs text-slate-700">
              {fill(hr.card.warningsChecked, {
                time: formatAgo(warningsChecked),
              })}{" "}
              · Izvor: DHMZ
            </p>
          </>
        )}
      </Section>

      <div className={`grid gap-2 py-1 ${compact ? "" : "md:grid-cols-2"}`}>
        {HAZARD_NAMES.map((name) => (
          <HazardCard key={name} name={name} card={card} />
        ))}
      </div>

      <Section title={hr.card.populationTitle}>
        <ul className="text-sm">
          <li>
            {population.total_rounded === 0
              ? hr.card.populationNone
              : population.below_threshold
                ? hr.card.populationSmall
                : fill(hr.card.populationTotal, {
                    value: formatNumber(population.total_rounded ?? 0),
                  })}
          </li>
          {population.total_rounded !== 0 && (
            <>
              <li>
                {fill(hr.card.share65, {
                  value: percent(population.share_65plus),
                })}
              </li>
              <li>
                {fill(hr.card.shareUnder15, {
                  value: percent(population.share_under15),
                })}
              </li>
              {population.age_share_source && (
                <li className="text-slate-700">
                  {
                    hr.card.shareSource[
                      population.age_share_source as "cell" | "naselje" | "jls"
                    ]
                  }
                </li>
              )}
            </>
          )}
        </ul>
      </Section>

      <Section title={hr.card.natureTitle}>
        {live.nature_nearby.length === 0 ? (
          <p className="text-sm">{hr.card.natureNone}</p>
        ) : (
          <ul className="text-sm">
            {live.nature_nearby.map((area) => (
              <li key={`${area.layer}-${area.name}`}>
                {area.name ?? "–"} (
                {hr.card.natureLayers[
                  area.layer as keyof typeof hr.card.natureLayers
                ] ?? area.layer}
                )
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title={hr.card.adviceTitle}>
        <div className="space-y-2 text-sm">
          {HAZARD_NAMES.map((name) => {
            const advice = card.advice[ADVICE_BY_HAZARD[name]];
            if (!advice) return null;
            return (
              <div key={name}>
                <h3 className="font-medium">{hr.card.hazards[name]}</h3>
                <ul className="list-disc pl-5">
                  {advice.items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
                <p className="text-xs text-slate-700">
                  <a
                    href={advice.url}
                    className="underline"
                    target="_blank"
                    rel="noreferrer"
                  >
                    {fill(hr.card.adviceSource, {
                      source: advice.source,
                      date: formatDate(advice.accessed),
                    })}
                  </a>
                </p>
              </div>
            );
          })}
        </div>
      </Section>

      <Section title={hr.about.disclaimerTitle}>
        <p className="text-sm">{hr.app.disclaimer}</p>
      </Section>

      <Actions card={card} />
    </div>
  );
}
