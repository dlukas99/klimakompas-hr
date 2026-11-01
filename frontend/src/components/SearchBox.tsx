import { useQuery } from "@tanstack/react-query";
import { useEffect, useId, useState, type KeyboardEvent } from "react";
import hr from "../i18n/hr.json";
import { fetchGeocode, type GeocodeResult } from "../lib/api/client";
import { formatNumber } from "../lib/format/number";

const DEBOUNCE_MS = 250;
const MIN_LENGTH = 2;

interface Props {
  onSelect: (result: GeocodeResult) => void;
}

export function SearchBox({ onSelect }: Props) {
  const id = useId();
  const listId = `${id}-list`;
  const statusId = `${id}-status`;
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);

  useEffect(() => {
    const timer = setTimeout(() => setQuery(input.trim()), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [input]);

  const enabled = query.length >= MIN_LENGTH;
  const { data, isFetching, isError } = useQuery({
    queryKey: ["geocode", query],
    queryFn: ({ signal }) => fetchGeocode(query, signal),
    enabled,
    retry: false,
    staleTime: 60 * 1000,
    gcTime: 60 * 1000,
  });
  const results = enabled ? (data?.results ?? []) : [];

  function choose(result: GeocodeResult) {
    setOpen(false);
    setActive(-1);
    setInput(result.label);
    onSelect(result);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      setOpen(false);
    } else if (event.key === "ArrowDown" && results.length > 0) {
      event.preventDefault();
      setOpen(true);
      setActive((index) => (index + 1) % results.length);
    } else if (event.key === "ArrowUp" && results.length > 0) {
      event.preventDefault();
      setOpen(true);
      setActive((index) => (index <= 0 ? results.length - 1 : index - 1));
    } else if (event.key === "Enter" && open && results.length > 0) {
      event.preventDefault();
      choose(results[Math.max(active, 0)]);
    }
  }

  let status = "";
  if (open && input.trim().length > 0 && input.trim().length < MIN_LENGTH)
    status = hr.search.minLength;
  else if (open && enabled) {
    if (isError) status = hr.search.error;
    else if (isFetching) status = hr.search.loading;
    else if (results.length === 0) status = hr.search.empty;
    else if (data?.addresses_searched === false)
      status = hr.search.addressesUnavailable;
  }
  const expanded = open && results.length > 0;

  return (
    <div className="relative w-full">
      <label htmlFor={id} className="sr-only">
        {hr.search.label}
      </label>
      <input
        id={id}
        type="search"
        role="combobox"
        aria-expanded={expanded}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={
          expanded && active >= 0 ? `${listId}-${active}` : undefined
        }
        aria-describedby={statusId}
        autoComplete="off"
        placeholder={hr.search.placeholder}
        value={input}
        onChange={(event) => {
          setInput(event.target.value);
          setOpen(true);
          setActive(-1);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
        className="w-full rounded-lg border border-slate-400 bg-white px-3 py-2 text-base text-slate-900 placeholder:text-slate-600 focus-visible:outline-2 focus-visible:outline-slate-900"
      />
      <div
        id={statusId}
        role="status"
        className={
          status
            ? "absolute z-30 mt-1 w-full rounded-lg bg-white px-3 py-2 text-sm text-slate-800 shadow-lg"
            : "sr-only"
        }
        style={expanded && status ? { position: "static" } : undefined}
      >
        {status}
      </div>
      <ul
        id={listId}
        role="listbox"
        aria-label={hr.search.results}
        hidden={!expanded}
        className="absolute z-30 mt-1 max-h-80 w-full overflow-y-auto rounded-lg bg-white text-slate-900 shadow-lg"
      >
        {results.map((result, index) => (
          <li
            key={`${result.kind}-${result.code ?? result.label}-${index}`}
            id={`${listId}-${index}`}
            role="option"
            aria-selected={index === active}
            // Keeps focus in the input, otherwise blur closes the list before the click lands.
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => choose(result)}
            className={`cursor-pointer px-3 py-2 text-sm ${index === active ? "bg-slate-200" : "hover:bg-slate-100"}`}
          >
            <span className="font-medium">{result.label}</span>
            <span className="block text-slate-700">
              {hr.search.kind[result.kind]}
              {result.detail ? ` · ${result.detail}` : ""}
              {result.population != null
                ? ` · ${formatNumber(result.population)} st.`
                : ""}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
