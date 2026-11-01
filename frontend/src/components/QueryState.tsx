import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import hr from "../i18n/hr.json";

interface Props<T> {
  query: UseQueryResult<T>;
  loading?: string;
  error?: (error: unknown) => string;
  children: (data: T) => ReactNode;
}

/** Loading and error states for a query, so no page ends up blank. */
export function QueryState<T>({ query, loading, error, children }: Props<T>) {
  if (query.isPending) {
    return <p role="status">{loading ?? hr.app.loading}</p>;
  }
  if (query.isError) {
    return (
      <div role="alert" className="rounded bg-amber-100 p-3 text-amber-950">
        <p>{error ? error(query.error) : hr.app.error}</p>
        <button
          type="button"
          onClick={() => void query.refetch()}
          className="mt-2 underline"
        >
          {hr.app.retry}
        </button>
      </div>
    );
  }
  return <>{children(query.data)}</>;
}
