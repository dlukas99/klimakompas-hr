import { useQuery } from "@tanstack/react-query";
import { QueryState } from "../components/QueryState";
import hr from "../i18n/hr.json";
import { fetchExports, fetchQuality, type SourceInfo } from "../lib/api/client";
import { useSources } from "../lib/api/hooks";
import { formatDateTime } from "../lib/format/date";
import { formatNumber } from "../lib/format/number";

const STATE_STYLE: Record<SourceInfo["state"], string> = {
  ok: "bg-green-100 text-green-950",
  stale: "bg-amber-100 text-amber-950",
  failed: "bg-red-100 text-red-950",
  static: "bg-green-100 text-green-950",
  browser: "bg-slate-200 text-slate-900",
  unused: "bg-slate-200 text-slate-900",
};

export function DataPage() {
  const sources = useSources();
  const quality = useQuery({
    queryKey: ["quality"],
    queryFn: ({ signal }) => fetchQuality(signal),
  });
  const exports = useQuery({
    queryKey: ["exports"],
    queryFn: ({ signal }) => fetchExports(signal),
  });
  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <h1 className="text-2xl font-bold">{hr.data.title}</h1>
      <p className="mt-1 text-slate-700">{hr.data.intro}</p>
      <section className="mt-4">
        <h2 className="text-xl font-semibold">{hr.data.sourcesTitle}</h2>
        <QueryState query={sources}>
          {(rows) => (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-slate-300 text-left">
                  <tr>
                    <th scope="col" className="px-2 py-1">
                      {hr.data.source}
                    </th>
                    <th scope="col" className="px-2 py-1">
                      {hr.data.publisher}
                    </th>
                    <th scope="col" className="px-2 py-1">
                      {hr.data.state}
                    </th>
                    <th scope="col" className="px-2 py-1">
                      {hr.data.refreshed}
                    </th>
                    <th scope="col" className="px-2 py-1">
                      {hr.data.license}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((source) => (
                    <tr
                      key={source.id}
                      className="border-b border-slate-100 align-top"
                    >
                      <td className="px-2 py-1">
                        {source.landing_url ? (
                          <a
                            href={source.landing_url}
                            className="underline"
                            target="_blank"
                            rel="noreferrer"
                          >
                            {source.name}
                          </a>
                        ) : (
                          source.name
                        )}
                      </td>
                      <td className="px-2 py-1">{source.publisher}</td>
                      <td className="px-2 py-1">
                        <span
                          className={`rounded px-2 py-0.5 whitespace-nowrap ${STATE_STYLE[source.state]}`}
                        >
                          {hr.data.states[source.state]}
                        </span>
                      </td>
                      <td className="px-2 py-1 whitespace-nowrap">
                        {source.last_success_at
                          ? formatDateTime(source.last_success_at)
                          : "–"}
                      </td>
                      <td className="px-2 py-1">
                        {source.portal_license ?? source.license}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </QueryState>
      </section>
      <section className="mt-6">
        <h2 className="text-xl font-semibold">{hr.data.qualityTitle}</h2>
        <p className="mt-1 text-slate-700">{hr.data.qualityIntro}</p>
        <QueryState query={quality}>
          {(rows) =>
            rows.length === 0 ? (
              <p className="mt-2">{hr.data.noQuality}</p>
            ) : (
              <div
                className="mt-2 max-h-96 overflow-auto"
                tabIndex={0}
                role="region"
                aria-label={hr.data.qualityTitle}
              >
                <table className="w-full text-sm">
                  <thead className="sticky top-0 border-b border-slate-300 bg-white text-left">
                    <tr>
                      <th scope="col" className="px-2 py-1">
                        {hr.data.source}
                      </th>
                      <th scope="col" className="px-2 py-1">
                        {hr.data.check}
                      </th>
                      <th scope="col" className="px-2 py-1">
                        {hr.data.state}
                      </th>
                      <th scope="col" className="px-2 py-1">
                        {hr.data.value}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr
                        key={`${row.source_id}-${row.check_id}`}
                        className="border-b border-slate-100"
                      >
                        <td className="px-2 py-1">{row.source_id}</td>
                        <td className="px-2 py-1">
                          {hr.data.checks[
                            row.check_id as keyof typeof hr.data.checks
                          ] ?? row.check_id}
                        </td>
                        <td className="px-2 py-1">
                          <span
                            className={`rounded px-2 py-0.5 ${row.status === "pass" ? STATE_STYLE.ok : STATE_STYLE.failed}`}
                          >
                            {row.status === "pass"
                              ? hr.data.pass
                              : hr.data.fail}
                          </span>
                        </td>
                        <td className="px-2 py-1">
                          {row.value == null ? "–" : formatNumber(row.value, 2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          }
        </QueryState>
      </section>
      <section className="mt-6">
        <h2 className="text-xl font-semibold">{hr.data.downloadsTitle}</h2>
        <p className="mt-1 text-slate-700">{hr.data.downloadsIntro}</p>
        <QueryState query={exports}>
          {(rows) => (
            <ul className="mt-2 space-y-2">
              {rows.map((dataset) => (
                <li
                  key={dataset.id}
                  className="rounded-lg border border-slate-200 p-3"
                >
                  <p className="font-medium">{dataset.title}</p>
                  <p className="text-sm">{dataset.description}</p>
                  <p className="mt-1 flex flex-wrap gap-3 text-sm">
                    {dataset.files.length === 0 && hr.data.noDownloads}
                    {dataset.files.map((file) => (
                      <a
                        key={file}
                        href={`/api/v1/export/${file}`}
                        className="underline"
                      >
                        {file}
                      </a>
                    ))}
                    <a
                      href={dataset.license}
                      className="underline"
                      target="_blank"
                      rel="noreferrer"
                    >
                      {hr.data.licenseLink}
                    </a>
                  </p>
                </li>
              ))}
            </ul>
          )}
        </QueryState>
      </section>
      <section className="mt-6">
        <h2 className="text-xl font-semibold">{hr.data.apiTitle}</h2>
        <ul className="mt-1 list-disc pl-5">
          <li>
            <a href="/api/docs" className="underline">
              {hr.data.api}
            </a>
          </li>
          <li>
            <a href="/api/v1/catalog.ttl" className="underline">
              {hr.data.catalog}
            </a>
          </li>
          <li>
            <a href="/ogc/" className="underline">
              {hr.data.ogc}
            </a>
          </li>
        </ul>
      </section>
    </div>
  );
}
