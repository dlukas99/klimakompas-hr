import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router";
import { LevelBadge } from "../components/LevelBadge";
import { QueryState } from "../components/QueryState";
import hr from "../i18n/hr.json";
import { fetchJlsList, type JlsListItem } from "../lib/api/client";
import { formatNumber } from "../lib/format/number";

type SortKey = "rank_hr" | "name" | "zupanija_name" | "pop";

function fold(value: string): string {
  return value
    .toLocaleLowerCase("hr-HR")
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/đ/g, "d");
}

function sorted(
  items: JlsListItem[],
  key: SortKey,
  ascending: boolean,
): JlsListItem[] {
  const direction = ascending ? 1 : -1;
  return [...items].sort((a, b) => {
    const left = a[key];
    const right = b[key];
    if (left == null) return 1;
    if (right == null) return -1;
    if (typeof left === "string") {
      return direction * left.localeCompare(String(right), "hr-HR");
    }
    return direction * (left - Number(right));
  });
}

export function JlsListPage() {
  const query = useQuery({
    queryKey: ["jls"],
    queryFn: ({ signal }) => fetchJlsList(signal),
    staleTime: 10 * 60 * 1000,
  });
  const [filter, setFilter] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; ascending: boolean }>({
    key: "rank_hr",
    ascending: true,
  });
  const needle = fold(filter.trim());
  const rows = useMemo(() => {
    const items = query.data ?? [];
    const matching = needle
      ? items.filter((item) =>
          fold(`${item.name} ${item.zupanija_name}`).includes(needle),
        )
      : items;
    return sorted(matching, sort.key, sort.ascending);
  }, [query.data, needle, sort]);

  function header(key: SortKey, label: string) {
    const active = sort.key === key;
    return (
      <th
        scope="col"
        className="px-2 py-1 text-left"
        aria-sort={
          active ? (sort.ascending ? "ascending" : "descending") : "none"
        }
      >
        <button
          type="button"
          className="font-semibold underline"
          title={hr.jls.sortBy}
          onClick={() =>
            setSort({
              key,
              ascending: active ? !sort.ascending : key !== "pop",
            })
          }
        >
          {label}
        </button>
      </th>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <h1 className="text-2xl font-bold">{hr.jls.listTitle}</h1>
      <p className="mt-1 text-slate-700">{hr.jls.listIntro}</p>
      <label className="mt-3 block max-w-md">
        <span className="font-medium">{hr.jls.filter}</span>
        <input
          type="search"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          className="mt-1 w-full rounded border border-slate-400 px-3 py-2"
        />
      </label>
      <QueryState query={query}>
        {() =>
          rows.length === 0 ? (
            <p className="mt-4">{hr.jls.empty}</p>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-slate-300">
                  <tr>
                    {header("rank_hr", hr.jls.rank)}
                    {header("name", hr.jls.name)}
                    {header("zupanija_name", hr.jls.zupanija)}
                    {header("pop", hr.jls.population)}
                    <th
                      scope="col"
                      className="px-2 py-1 text-left font-semibold"
                    >
                      {hr.jls.class}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.code} className="border-b border-slate-100">
                      <td className="px-2 py-1">{row.rank_hr ?? "–"}</td>
                      <td className="px-2 py-1">
                        <Link to={`/opcine/${row.code}`} className="underline">
                          {row.name}
                        </Link>{" "}
                        <span className="text-slate-700">
                          (
                          {row.kind === "grad"
                            ? hr.jls.kindGrad
                            : hr.jls.kindOpcina}
                          )
                        </span>
                      </td>
                      <td className="px-2 py-1">{row.zupanija_name}</td>
                      <td className="px-2 py-1">
                        {row.pop == null ? "–" : formatNumber(row.pop)}
                      </td>
                      <td className="px-2 py-1">
                        <LevelBadge level={row.ikr_class} compact />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        }
      </QueryState>
    </div>
  );
}
