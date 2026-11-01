import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { LevelBadge } from "../components/LevelBadge";
import { QueryState } from "../components/QueryState";
import { HAZARD_NAMES } from "../features/card/weights";
import { MapView } from "../features/map/MapView";
import type { Bbox } from "../features/map/urlState";
import hr from "../i18n/hr.json";
import {
  ApiError,
  fetchJls,
  fetchJlsCells,
  fetchJlsNaselja,
  type JlsDetail,
} from "../lib/api/client";
import { downloadCsv, toCsv } from "../lib/format/csv";
import { formatNumber } from "../lib/format/number";
import { fill } from "../lib/format/template";

function Profile({ detail }: { detail: JlsDetail }) {
  const data = HAZARD_NAMES.map((name) => ({
    name: hr.card.hazards[name],
    jls: detail.profile.jls[name],
    zupanija: detail.profile.zupanija[name],
    hr: detail.profile.hr[name],
  }));
  return (
    <section className="mt-6">
      <h2 className="text-xl font-semibold">{hr.jls.profileTitle}</h2>
      <div className="mt-2 h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="name" />
            <YAxis
              domain={[0, 1]}
              tickFormatter={(value: number) => formatNumber(value, 1)}
            />
            <Tooltip formatter={(value) => formatNumber(Number(value), 3)} />
            <Legend />
            <Bar dataKey="jls" name={hr.jls.profileJls} fill="#bd0026" />
            <Bar dataKey="zupanija" name={hr.jls.profileZup} fill="#fd8d3c" />
            <Bar dataKey="hr" name={hr.jls.profileHr} fill="#64748b" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table className="mt-2 w-full text-sm">
        <caption className="sr-only">{hr.jls.profileTitle}</caption>
        <thead>
          <tr className="border-b border-slate-300 text-left">
            <th scope="col" className="px-2 py-1">
              {hr.jls.profileHazard}
            </th>
            <th scope="col" className="px-2 py-1">
              {hr.jls.profileJls}
            </th>
            <th scope="col" className="px-2 py-1">
              {hr.jls.profileZup}
            </th>
            <th scope="col" className="px-2 py-1">
              {hr.jls.profileHr}
            </th>
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr key={row.name} className="border-b border-slate-100">
              <th scope="row" className="px-2 py-1 text-left font-medium">
                {row.name}
              </th>
              <td className="px-2 py-1">
                {row.jls == null ? "–" : formatNumber(row.jls, 3)}
              </td>
              <td className="px-2 py-1">
                {row.zupanija == null ? "–" : formatNumber(row.zupanija, 3)}
              </td>
              <td className="px-2 py-1">
                {row.hr == null ? "–" : formatNumber(row.hr, 3)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function Naselja({ code, name }: { code: string; name: string }) {
  const query = useQuery({
    queryKey: ["jls", code, "naselja"],
    queryFn: ({ signal }) => fetchJlsNaselja(code, signal),
  });
  const [filter, setFilter] = useState("");
  return (
    <section className="mt-6">
      <h2 className="text-xl font-semibold">{hr.jls.naseljaTitle}</h2>
      <QueryState query={query}>
        {(rows) => {
          const needle = filter.trim().toLocaleLowerCase("hr-HR");
          const visible = needle
            ? rows.filter((row) =>
                row.name.toLocaleLowerCase("hr-HR").includes(needle),
              )
            : rows;
          return (
            <>
              <div className="mt-2 flex flex-wrap items-end gap-2 print:hidden">
                <label className="min-w-0 flex-1">
                  <span className="text-sm font-medium">{hr.jls.filter}</span>
                  <input
                    type="search"
                    value={filter}
                    onChange={(event) => setFilter(event.target.value)}
                    className="mt-1 w-full rounded border border-slate-400 px-3 py-1"
                  />
                </label>
                <button
                  type="button"
                  className="rounded border border-slate-400 px-3 py-1 text-sm"
                  onClick={() =>
                    downloadCsv(
                      `naselja-${name}.csv`,
                      toCsv(
                        [
                          hr.jls.naselje,
                          hr.jls.population,
                          hr.jls.ikr,
                          hr.jls.class,
                        ],
                        rows.map((row) => [
                          row.name,
                          row.pop,
                          row.ikr,
                          row.ikr_class,
                        ]),
                      ),
                    )
                  }
                >
                  {hr.jls.exportNaselja}
                </button>
              </div>
              <div
                className="mt-2 max-h-96 overflow-auto print:max-h-none"
                tabIndex={0}
                role="region"
                aria-label={hr.jls.naseljaTitle}
              >
                <table className="w-full text-sm">
                  <thead className="sticky top-0 border-b border-slate-300 bg-white text-left">
                    <tr>
                      <th scope="col" className="px-2 py-1">
                        {hr.jls.naselje}
                      </th>
                      <th scope="col" className="px-2 py-1">
                        {hr.jls.population}
                      </th>
                      <th scope="col" className="px-2 py-1">
                        {hr.jls.class}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {visible.map((row) => (
                      <tr key={row.code} className="border-b border-slate-100">
                        <td className="px-2 py-1">{row.name}</td>
                        <td className="px-2 py-1">
                          {row.pop == null ? "–" : formatNumber(row.pop)}
                        </td>
                        <td className="px-2 py-1">
                          {row.ikr_class ? (
                            <LevelBadge level={row.ikr_class} compact />
                          ) : (
                            <span className="text-slate-700">
                              {hr.jls.noIndex}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          );
        }}
      </QueryState>
    </section>
  );
}

function CellsExport({ code, name }: { code: string; name: string }) {
  const query = useQuery({
    queryKey: ["jls", code, "cells"],
    queryFn: ({ signal }) => fetchJlsCells(code, signal),
  });
  if (!query.data) return null;
  const rows = query.data;
  return (
    <button
      type="button"
      className="rounded border border-slate-400 px-3 py-1 text-sm"
      onClick={() =>
        downloadCsv(
          `celije-${name}.csv`,
          toCsv(
            [
              hr.jls.cellId,
              hr.jls.naselje,
              hr.jls.population,
              hr.jls.ikr,
              hr.jls.class,
              hr.card.hazards.flood,
              hr.card.hazards.heat,
              hr.card.hazards.fire,
              hr.card.hazards.air,
            ],
            rows.map((row) => [
              row.cell_id,
              row.naselje,
              row.pop_total ?? hr.jls.underTen,
              row.ikr,
              row.ikr_class,
              row.class_flood,
              row.class_heat,
              row.class_fire,
              row.class_air,
            ]),
          ),
        )
      }
    >
      {hr.jls.exportCells}
    </button>
  );
}

function Detail({ detail }: { detail: JlsDetail }) {
  return (
    <>
      <header>
        <p className="text-sm text-slate-700">
          {detail.kind === "grad" ? hr.jls.kindGrad : hr.jls.kindOpcina},{" "}
          {detail.zupanija.name}
        </p>
        <h1 className="text-2xl font-bold">{detail.name}</h1>
      </header>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg bg-slate-100 p-3">
          <h2 className="font-semibold">{hr.jls.population}</h2>
          <p className="text-2xl font-bold">
            {detail.pop == null ? "–" : formatNumber(detail.pop)}
          </p>
          {detail.pop65 != null && (
            <p>
              {hr.jls.pop65}: {formatNumber(detail.pop65)}
            </p>
          )}
        </div>
        <div className="rounded-lg bg-slate-100 p-3">
          <h2 className="font-semibold">{hr.jls.ikrTitle}</h2>
          <div className="mt-1">
            <LevelBadge level={detail.ikr_class} />
          </div>
          {detail.rank_hr && (
            <p className="mt-1">
              {fill(hr.jls.rankHr, {
                rank: detail.rank_hr,
                total: detail.total_hr,
              })}
            </p>
          )}
          {detail.rank_zup && (
            <p>
              {fill(hr.jls.rankZup, {
                rank: detail.rank_zup,
                total: detail.total_zup,
              })}
            </p>
          )}
        </div>
      </div>
      <section className="mt-6">
        <h2 className="text-xl font-semibold">{hr.jls.exposedTitle}</h2>
        <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {HAZARD_NAMES.map((name) => {
            const exposed = detail.exposed[name];
            return (
              <div
                key={name}
                className="rounded-lg border border-slate-200 p-3"
              >
                <h3 className="font-medium">{hr.card.hazards[name]}</h3>
                <p className="text-xl font-bold">
                  {exposed ? formatNumber(Math.round(exposed.pop)) : "–"}
                </p>
                {exposed && (
                  <p className="text-sm text-slate-700">
                    {fill(hr.jls.exposedOf65, {
                      value: formatNumber(Math.round(exposed.pop65)),
                    })}
                  </p>
                )}
              </div>
            );
          })}
        </div>
        <p className="mt-2 text-sm text-slate-700">{hr.jls.exposedNote}</p>
      </section>
      <div className="relative mt-6 h-80 overflow-hidden rounded-lg print:hidden">
        <ErrorBoundary message={hr.map.unavailable}>
          <MapView
            layer="ikr"
            overlays={["jls"]}
            view={null}
            bbox={detail.bbox as Bbox}
            pin={null}
            attribution=""
          />
        </ErrorBoundary>
      </div>
      <p className="mt-1 text-sm print:hidden">
        <Link
          to={`/karta?okvir=${detail.bbox.join(",")}`}
          className="underline"
        >
          {hr.jls.openMap}
        </Link>
      </p>
      <Profile detail={detail} />
      <section className="mt-6">
        <h2 className="text-xl font-semibold">{hr.jls.attentionTitle}</h2>
        {detail.attention.length === 0 ? (
          <p className="mt-1">{hr.jls.attentionNone}</p>
        ) : (
          <>
            <ul className="mt-1 list-disc space-y-1 pl-5">
              {detail.attention.map((item) => (
                <li key={item.hazard}>
                  {item.text}{" "}
                  {item.url && (
                    <a
                      href={item.url}
                      className="underline"
                      target="_blank"
                      rel="noreferrer"
                    >
                      {hr.jls.attentionMore}
                    </a>
                  )}
                </li>
              ))}
            </ul>
            <p className="mt-1 text-sm text-slate-700">
              {hr.jls.attentionNote}
            </p>
          </>
        )}
      </section>
      <Naselja code={detail.code} name={detail.name} />
      <div className="mt-4 flex flex-wrap gap-2 print:hidden">
        <CellsExport code={detail.code} name={detail.name} />
        <button
          type="button"
          onClick={() => window.print()}
          className="rounded border border-slate-400 px-3 py-1 text-sm"
        >
          {hr.jls.print}
        </button>
      </div>
      <p className="mt-4 text-sm text-slate-700">
        {fill(hr.jls.source, { version: detail.index_version ?? "–" })}
      </p>
      <p className="mt-2 text-sm text-slate-700">{hr.app.disclaimer}</p>
    </>
  );
}

export function JlsPage() {
  const { code = "" } = useParams();
  const query = useQuery({
    queryKey: ["jls", code],
    queryFn: ({ signal }) => fetchJls(code, signal),
    retry: false,
  });
  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <QueryState
        query={query}
        error={(error) =>
          error instanceof ApiError && error.status === 404
            ? hr.jls.notFound
            : hr.app.error
        }
      >
        {(detail) => <Detail detail={detail} />}
      </QueryState>
    </div>
  );
}
