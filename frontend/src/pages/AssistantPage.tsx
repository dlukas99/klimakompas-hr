import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { SearchBox } from "../components/SearchBox";
import { cardLink } from "../features/map/mapLink";
import hr from "../i18n/hr.json";
import {
  ApiError,
  fetchAgentStatus,
  fetchQuick,
  streamChat,
  type ChatAnswer,
  type Citation,
  type GeocodeOptions,
  type GeocodeResult,
  type QuickAnswer,
  type QuickId,
} from "../lib/api/client";

const QUICK_IDS: QuickId[] = [
  "older_exposed",
  "hottest",
  "air_near",
  "warnings",
  "flood_data",
];
const NEEDS_JLS: QuickId[] = ["older_exposed", "hottest"];

function Citations({ items }: { items: Citation[] }) {
  if (items.length === 0) return null;
  return (
    <div className="mt-2 text-xs text-slate-700">
      <p className="font-medium">{hr.assistant.sources}</p>
      <ol className="list-decimal pl-4">
        {items.map((item) => (
          <li key={item.n}>
            {item.url ? (
              <a
                href={item.url}
                className="underline"
                target="_blank"
                rel="noreferrer"
              >
                {item.title}
              </a>
            ) : (
              item.title
            )}{" "}
            ({item.publisher})
          </li>
        ))}
      </ol>
    </div>
  );
}

const JLS_ONLY: GeocodeOptions = { kinds: ["municipality"] };

function QuickQuestions() {
  const [jls, setJls] = useState<GeocodeResult | null>(null);
  const [place, setPlace] = useState<GeocodeResult | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const placeOptions = useMemo<GeocodeOptions>(
    () => ({ kinds: ["address", "settlement"], jls: jls?.code ?? undefined }),
    [jls],
  );
  const ask = useMutation<QuickAnswer, Error, QuickId>({
    mutationFn: (question) => {
      // Without an address, the air question is about the chosen municipality's main settlement.
      const point = place ?? jls;
      return fetchQuick(question, {
        jls: jls?.code ?? undefined,
        lat: point?.lat,
        lon: point?.lon,
      });
    },
  });

  function onJls(result: GeocodeResult) {
    setJls(result);
    setPlace(null);
    setNotice(null);
  }

  function onAsk(question: QuickId) {
    if (NEEDS_JLS.includes(question) && !jls) {
      setNotice(hr.assistant.pickJls);
      return;
    }
    setNotice(null);
    ask.mutate(question);
  }

  return (
    <section>
      <h2 className="text-xl font-semibold">{hr.assistant.quickTitle}</h2>
      <p className="text-sm text-slate-700">{hr.assistant.quickIntro}</p>
      <div className="mt-2 grid gap-3 sm:grid-cols-2">
        <div>
          <SearchBox
            onSelect={onJls}
            label={hr.assistant.jlsLabel}
            placeholder={hr.assistant.jlsPlaceholder}
            options={JLS_ONLY}
            visibleLabel
          />
          {jls && (
            <p className="mt-1 text-sm text-slate-700" data-testid="chosen-jls">
              {jls.label}, {jls.detail}
            </p>
          )}
        </div>
        <div>
          {/* Remounting clears a suggestion list left over from another municipality. */}
          <SearchBox
            key={jls?.code ?? "none"}
            onSelect={setPlace}
            label={hr.assistant.placeLabel}
            placeholder={
              jls ? hr.assistant.placePlaceholder : hr.assistant.placeDisabled
            }
            options={placeOptions}
            disabled={!jls}
            visibleLabel
          />
          {place && (
            <p className="mt-1 text-sm text-slate-700">{place.label}</p>
          )}
        </div>
      </div>
      <ul className="mt-3 space-y-1">
        {QUICK_IDS.map((id) => (
          <li key={id}>
            <button
              type="button"
              onClick={() => onAsk(id)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-left hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-slate-900"
            >
              {hr.assistant.quick[id]}
            </button>
          </li>
        ))}
      </ul>
      <div aria-live="polite" className="mt-3">
        {notice && (
          <p className="rounded bg-amber-100 p-2 text-amber-950">{notice}</p>
        )}
        {ask.isPending && <p>{hr.assistant.thinking}</p>}
        {ask.isError && (
          <p className="rounded bg-amber-100 p-2 text-amber-950">
            {hr.app.error}
          </p>
        )}
        {ask.data && !notice && (
          <div
            className="rounded-lg bg-slate-100 p-3"
            data-testid="quick-answer"
          >
            <p>{ask.data.text}</p>
            <Citations items={ask.data.citations} />
          </div>
        )}
      </div>
    </section>
  );
}

interface Turn {
  question: string;
  answer: ChatAnswer | null;
  error: string | null;
}

function Chat() {
  const status = useQuery({
    queryKey: ["agent-status"],
    queryFn: ({ signal }) => fetchAgentStatus(signal),
    retry: false,
    staleTime: 60 * 1000,
  });
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [tool, setTool] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const question = input.trim();
    if (!question || busy) return;
    setInput("");
    setBusy(true);
    setTool(null);
    let answer: ChatAnswer | null = null;
    let error: string | null = null;
    try {
      answer = await streamChat(question, setTool);
      if (!answer) error = hr.assistant.unavailable;
    } catch (failure) {
      error =
        failure instanceof ApiError && failure.status === 429
          ? hr.assistant.rateLimited
          : hr.assistant.unavailable;
    }
    setTurns((current) => [...current, { question, answer, error }]);
    setBusy(false);
    setTool(null);
  }

  return (
    <section>
      <h2 className="text-xl font-semibold">{hr.assistant.chatTitle}</h2>
      <p className="text-sm text-slate-700">{hr.assistant.chatHelp}</p>
      {status.data && !status.data.llm_available && (
        <p className="mt-1 text-sm text-slate-700" data-testid="no-model">
          {hr.assistant.noModel}
        </p>
      )}
      <div aria-live="polite" className="mt-2 space-y-3">
        {turns.map((turn, index) => (
          <div key={`${index}-${turn.question}`}>
            <p className="font-medium">
              {hr.assistant.you}: {turn.question}
            </p>
            {turn.error && (
              <p className="rounded bg-amber-100 p-2 text-amber-950">
                {turn.error}
              </p>
            )}
            {turn.answer && (
              <div
                className="mt-1 rounded-lg bg-slate-100 p-3"
                data-testid="chat-answer"
              >
                <p className="whitespace-pre-line">{turn.answer.text}</p>
                {turn.answer.map_actions.map((action) => (
                  <Link
                    key={action.label}
                    to={cardLink(action.lat, action.lon, action.label)}
                    className="mt-1 block text-sm underline"
                  >
                    {hr.assistant.showOnMap}: {action.label}
                  </Link>
                ))}
                <Citations items={turn.answer.citations} />
              </div>
            )}
          </div>
        ))}
        {busy && (
          <p role="status">
            {tool
              ? `${hr.assistant.tool} ${hr.assistant.toolNames[tool as keyof typeof hr.assistant.toolNames] ?? tool}`
              : hr.assistant.thinking}
          </p>
        )}
      </div>
      <form
        onSubmit={(event) => void onSubmit(event)}
        className="mt-3 flex flex-wrap gap-2"
      >
        <label className="min-w-0 flex-1 basis-60">
          <span className="sr-only">{hr.assistant.chatLabel}</span>
          <input
            value={input}
            maxLength={1000}
            onChange={(event) => setInput(event.target.value)}
            placeholder={hr.assistant.chatPlaceholder}
            className="w-full rounded-lg border border-slate-400 px-3 py-2 placeholder:text-slate-600"
          />
        </label>
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-white disabled:opacity-60"
        >
          {hr.assistant.send}
        </button>
      </form>
      <p className="mt-2 text-sm text-slate-700">{hr.assistant.notice}</p>
    </section>
  );
}

export function AssistantPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
      <div>
        <h1 className="text-2xl font-bold">{hr.assistant.title}</h1>
        <p className="mt-1 text-slate-700">{hr.assistant.intro}</p>
      </div>
      <Chat />
      <QuickQuestions />
    </div>
  );
}
