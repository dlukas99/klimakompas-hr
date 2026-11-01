import { Link, useNavigate } from "react-router";
import { SearchBox } from "../components/SearchBox";
import { cardLink } from "../features/map/mapLink";
import hr from "../i18n/hr.json";
import { useSources, useWarnings } from "../lib/api/hooks";

const USED_SOURCE_STATES = new Set(["ok", "stale", "static", "browser"]);

function WarningsStrip() {
  const { data, isError } = useWarnings();
  if (isError || !data) return null;
  const areas = new Set(data.warnings.map((warning) => warning.area_desc));
  return (
    <section
      aria-label={hr.home.warningsTitle}
      className="rounded-lg border border-amber-300 bg-amber-50 p-3"
    >
      <h2 className="font-semibold">{hr.home.warningsTitle}</h2>
      {data.warnings.length === 0 ? (
        <p>{hr.home.warningsNone}</p>
      ) : (
        <p>
          {hr.home.warningsCount} {areas.size} {hr.home.warningsAreas}:{" "}
          {[...areas].slice(0, 6).join(", ")}
          {areas.size > 6 ? " …" : ""}
        </p>
      )}
    </section>
  );
}

export function HomePage() {
  const navigate = useNavigate();
  const { data: sources } = useSources();
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8">
      <div>
        <h1 className="text-3xl font-bold">{hr.home.title}</h1>
        <p className="mt-2 text-lg text-slate-700">{hr.home.subtitle}</p>
      </div>
      <SearchBox
        onSelect={(result) =>
          navigate(cardLink(result.lat, result.lon, result.label))
        }
      />
      <Link
        to="/karta"
        className="self-start rounded-lg bg-slate-900 px-4 py-2 font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900"
      >
        {hr.home.openMap}
      </Link>
      <WarningsStrip />
      <section>
        <h2 className="text-xl font-semibold">{hr.home.howTitle}</h2>
        <ol className="mt-2 list-decimal space-y-1 pl-5">
          {hr.home.how.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </section>
      <section className="rounded-lg bg-slate-100 p-4">
        <h2 className="text-xl font-semibold">{hr.home.jlsTitle}</h2>
        <p className="mt-1">{hr.home.jlsText}</p>
        <Link to="/opcine" className="mt-2 inline-block font-medium underline">
          {hr.home.jlsCta}
        </Link>
      </section>
      {sources && (
        <section>
          <h2 className="text-xl font-semibold">{hr.home.sourcesTitle}</h2>
          <p className="mt-1 text-sm text-slate-700">
            {[
              ...new Set(
                sources
                  .filter((source) => USED_SOURCE_STATES.has(source.state))
                  .map((source) => source.publisher),
              ),
            ].join(" · ")}
          </p>
        </section>
      )}
      <p className="text-sm text-slate-700">{hr.app.disclaimer}</p>
    </div>
  );
}
