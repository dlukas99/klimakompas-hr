import { Link, useSearchParams } from "react-router";
import { QueryState } from "../components/QueryState";
import { CardView } from "../features/card/CardView";
import { useCard } from "../features/card/useCard";
import hr from "../i18n/hr.json";
import { ApiError } from "../lib/api/client";

function coordinate(value: string | null): number | null {
  if (value === null || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function CardPage() {
  const [params] = useSearchParams();
  const lat = coordinate(params.get("lat"));
  const lon = coordinate(params.get("lon"));
  const label = params.get("naziv");
  const card = useCard(lat, lon, label);
  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      {lat === null || lon === null ? (
        <p>
          {hr.card.missingLocation}{" "}
          <Link to="/karta" className="underline">
            {hr.home.openMap}
          </Link>
        </p>
      ) : (
        <>
          <QueryState
            query={card}
            loading={hr.card.loading}
            error={(error) =>
              error instanceof ApiError &&
              (error.status === 404 || error.status === 422)
                ? hr.card.outside
                : hr.card.error
            }
          >
            {(data) => <CardView card={data} />}
          </QueryState>
          <p className="mt-4 print:hidden">
            <Link to={`/karta?oznaka=${lat},${lon}`} className="underline">
              {hr.card.showOnMap}
            </Link>
          </p>
        </>
      )}
    </div>
  );
}
