import { Link, useNavigate } from "react-router";
import { SearchBox } from "../components/SearchBox";
import { searchResultParams } from "../features/map/mapLink";
import hr from "../i18n/hr.json";

export function HomePage() {
  const navigate = useNavigate();
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 px-4 py-10">
      <h1 className="text-3xl font-bold">{hr.home.title}</h1>
      <p className="text-lg text-slate-700">{hr.home.subtitle}</p>
      <SearchBox
        onSelect={(result) =>
          navigate(
            `/karta?${searchResultParams(result, new URLSearchParams())}`,
          )
        }
      />
      <Link
        to="/karta"
        className="self-start rounded-lg bg-slate-900 px-4 py-2 font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900"
      >
        {hr.home.openMap}
      </Link>
      <p className="mt-6 text-sm text-slate-700">{hr.app.disclaimer}</p>
    </div>
  );
}
