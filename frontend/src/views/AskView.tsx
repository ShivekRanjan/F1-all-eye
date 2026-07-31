import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { Button } from "../components/Button";
import { Callout, Card, EmptyState, Metric } from "../components/ui";
import { DataTable, type Column } from "../components/DataTable";
import { ChatIcon } from "../components/NavIcons";
import { beatsPick, clock, compoundColor, fmtPlan, pct } from "../lib/format";
import type {
  AskResp,
  DegradationResp,
  DriverStanding,
  ParsedQuery,
  RaceCardResp,
  RecommendResp,
  ShortlistRow,
  StandingsResp,
  UndercutResp,
  UpcomingPred,
  UpcomingResp,
} from "../api/types";
import { ViewIntro } from "./common";

/** The natural-language front door to the same engine every other view drives.
 *
 *  Thin, like `api.py`: this file parses nothing and models nothing. It sends a
 *  sentence to `/ask` and renders what comes back. The intent + slots are shown
 *  on every answer, because a fuzzy parse that silently hears "Monaco" for
 *  "Monza" produces a confident wrong answer, and the only defence is letting
 *  the user see what was understood. */

/** Ordered so the shipped default reads first. */
const PARSERS = ["hybrid", "rules", "transformer"] as const;
type Parser = (typeof PARSERS)[number];

type Turn =
  | { role: "you"; text: string }
  | { role: "engine"; answer: AskResp }
  | { role: "error"; text: string };

const EXAMPLES = [
  "fastest strategy for Monza",
  "how do the tyres go off at Zandvoort",
  "who leads the championship",
  "what happened at Silverstone",
  "lap 30 at Monza, I'm on mediums 18 laps, Verstappen on softs 4 laps — do I box?",
];

const SLOT_LABEL: Record<string, string> = {
  track: "circuit",
  season: "season",
  current_lap: "lap",
  objective: "objective",
  max_stops: "max stops",
  track_temp: "track temp °C",
  gap_s: "gap",
  your_compound: "your tyre",
  your_age: "your age",
  your_new_compound: "you fit",
  rival_compound: "rival tyre",
  rival_age: "rival age",
  rival_new_compound: "rival fits",
  rival_pit_lap: "rival pits",
  rival_driver: "rival",
  driver: "driver",
};

const STORAGE_KEY = "f1se.ask.turns";

export default function AskView() {
  // Views are lazy-mounted and unmount on tab switch, so without this a trip to
  // Strategy and back wipes the conversation. Session (not local) storage: the
  // transcript is worth keeping across a tab switch, not across a week.
  const [turns, setTurns] = useState<Turn[]>(() => {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      return raw ? (JSON.parse(raw) as Turn[]) : [];
    } catch {
      return [];
    }
  });
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [parser, setParser] = useState<Parser>("hybrid");

  // Two kinds of thread, and they are not the same thing.
  //
  // `pending` is an *unfinished* question: the engine asked for a missing slot,
  // so the reply is appended here before sending. `lastAnswered` is a *finished*
  // one, kept because conversation does not restate — after "fastest strategy
  // for Silverstone" the next thing a person says is "but the temperature is 35
  // degrees", which means nothing on its own. That goes to the server as
  // `context`, and the server decides whether it is a refinement or a new
  // question; the client does not guess.
  const [pending, setPending] = useState<string | null>(null);
  const [lastAnswered, setLastAnswered] = useState<string | null>(null);

  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(turns));
    } catch {
      /* quota / private mode — the transcript is a convenience, not state */
    }
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  async function send(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    const full = pending ? `${pending} ${q}` : q;
    setTurns((t) => [...t, { role: "you", text: q }]);
    setInput("");
    setBusy(true);
    try {
      const answer = await api.ask(full, parser, pending ? null : lastAnswered);
      setTurns((t) => [...t, { role: "engine", answer }]);
      const unfinished = answer.needs.length > 0 && answer.parsed.intent !== "unknown";
      // Still short of a required slot: keep accumulating. Otherwise the thread
      // is resolved and the next question starts clean.
      setPending(unfinished ? full : null);
      // Remember what was actually answered so the next message can refine it.
      // A merged answer replaces the context with the combined question, so
      // refinements chain: circuit, then temperature, then stop count.
      if (!unfinished && answer.parsed.intent !== "unknown") {
        setLastAnswered(answer.merged_with_context && lastAnswered ? `${lastAnswered} ${q}` : full);
      }
    } catch (e) {
      setTurns((t) => [...t, { role: "error", text: e instanceof Error ? e.message : String(e) }]);
      setPending(null);
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  function reset() {
    setTurns([]);
    setPending(null);
    setLastAnswered(null);
    sessionStorage.removeItem(STORAGE_KEY);
    inputRef.current?.focus();
  }

  return (
    <div className="space-y-5">
      <ViewIntro>
        Ask the engine a strategy question in plain English — it parses the sentence into an intent
        and slots, runs the <strong>same</strong> simulator the Strategy and Undercut views drive,
        and answers in a sentence with the numbers underneath. Every answer shows what was
        understood, so a misheard circuit is obvious rather than silent.
      </ViewIntro>

      <div className="flex flex-wrap items-center gap-2">
        <ParserToggle value={parser} onChange={setParser} />
        {turns.length > 0 && (
          <Button variant="ghost" size="sm" onClick={reset} className="ml-auto">
            Clear
          </Button>
        )}
      </div>

      {turns.length === 0 ? (
        <div className="space-y-4">
          <EmptyState
            icon={<ChatIcon width={28} height={28} />}
            title="Ask about strategy, tyres, standings or a past race."
            hint="It answers six kinds of question. Try one of these to see the shape of an answer."
          />
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((e) => (
              <button
                key={e}
                onClick={() => send(e)}
                className="rounded-md border border-line-ctl px-3 py-1.5 text-left text-data text-ink-dim transition hover:border-line-hover hover:text-ink"
              >
                {e}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {turns.map((t, i) => (
            <TurnRow key={i} turn={t} />
          ))}
          {busy && (
            <div role="status" aria-live="polite" className="flex items-center gap-2 text-sm text-ink-muted">
              <span className="h-1.5 w-1.5 animate-f1pulse rounded-full bg-accent" />
              Running the engine…
            </div>
          )}
          <div ref={endRef} />
        </div>
      )}

      <Composer
        inputRef={inputRef}
        value={input}
        onChange={setInput}
        onSend={() => send(input)}
        busy={busy}
        pending={pending}
      />
    </div>
  );
}

// --- composer ---------------------------------------------------------------

function Composer({
  inputRef,
  value,
  onChange,
  onSend,
  busy,
  pending,
}: {
  // A named prop, not `ref` — this is React 18, where `ref` on a function
  // component is not forwarded and would silently arrive undefined.
  inputRef: React.RefObject<HTMLInputElement>;
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  busy: boolean;
  pending: string | null;
}) {
  return (
    // Sticky so the composer is reachable without scrolling to the end of a
    // long transcript. The gradient matches the page (not card) background so
    // the fade reads as the page, and briefly occludes the ambient grid drift
    // rather than letting it run under the input.
    <div className="sticky bottom-0 -mx-1 bg-gradient-to-t from-surface-page via-surface-page to-transparent px-1 pb-1 pt-4">
      {pending && (
        // The slot-filling trick is invisible otherwise: the user typed "lap 30"
        // but the engine received their whole original question. Say so.
        <div className="mb-2 flex items-center gap-2 font-mono text-mini text-ink-faint">
          <span className="h-[5px] w-[5px] rounded-full bg-accent" />
          following up on “{pending}”
        </div>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSend();
        }}
        className="flex items-center gap-2"
      >
        <input
          ref={inputRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Ask about a strategy, a tyre, a rival…"
          aria-label="Ask the engine a question"
          className="min-w-0 flex-1 rounded-md border border-line-ctl bg-surface-inset px-3 py-2 text-sm text-ink placeholder:text-ink-fainter focus:border-accent/60 focus:outline-none"
        />
        <Button type="submit" variant="primary" loading={busy} disabled={!value.trim() && !busy}>
          Ask
        </Button>
      </form>
    </div>
  );
}

const PARSER_HELP: Record<Parser, string> = {
  hybrid:
    "Ships. Transformer picks the intent, the rule parser fills the slots — each the half that measurably won across three seeds (METHODOLOGY §15).",
  rules:
    "Hand-written rules alone. Perfect slot precision, but reads the intent correctly on only about half of unseen phrasings.",
  transformer:
    "The from-scratch transformer alone. Best intent accuracy, slightly lower slot precision. Kept switchable so the comparison is reproducible.",
};

function ParserToggle({ value, onChange }: { value: Parser; onChange: (v: Parser) => void }) {
  return (
    <div className="flex items-center gap-2">
      <span className="font-mono text-mini uppercase tracking-[0.14em] text-ink-faint">parser</span>
      {PARSERS.map((p) => (
        <Button
          key={p}
          size="sm"
          variant="ghost"
          pressed={value === p}
          onClick={() => onChange(p)}
          // aria-label, not just title: the visible word is "rules", which says
          // nothing on its own about what the control does.
          aria-label={`Use the ${p} parser`}
          title={PARSER_HELP[p]}
        >
          {p}
        </Button>
      ))}
    </div>
  );
}

// --- turns ------------------------------------------------------------------

function TurnRow({ turn }: { turn: Turn }) {
  if (turn.role === "you") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] animate-rise rounded-lg rounded-br-sm border border-line-ctl bg-surface-inset px-3 py-2 text-sm text-ink-soft">
          {turn.text}
        </div>
      </div>
    );
  }
  if (turn.role === "error") {
    return (
      <Card className="animate-rise border-l-2 border-l-amber-400 p-4">
        <div className="font-mono text-mini uppercase tracking-[0.16em] text-amber-300">
          Engine error
        </div>
        <div className="mt-1.5 text-sm text-ink">{turn.text}</div>
      </Card>
    );
  }

  const a = turn.answer;
  const asking = a.needs.length > 0;
  return (
    <Card className={`animate-rise p-4 ${asking ? "" : "border-l-2 border-l-accent"}`}>
      <p className="text-sm leading-relaxed text-ink">{a.text}</p>
      {a.note && (
        <div className="mt-3">
          <Callout tone="warn">{a.note}</Callout>
        </div>
      )}
      {a.merged_with_context && <MergedNote />}
      {a.data && !asking && <AnswerData intent={a.parsed.intent} data={a.data} />}
      <Understood parsed={a.parsed} />
    </Card>
  );
}

/** The parse, shown on every answer. Not debug output — the user's only way to
 *  check the question they asked is the question that got answered. */
function Understood({ parsed }: { parsed: ParsedQuery }) {
  const slots = Object.entries(parsed.slots).filter(([k]) => k !== "other_rivals");
  return (
    <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-line pt-3">
      <span className="font-mono text-micro uppercase tracking-[0.14em] text-ink-fainter">
        understood as
      </span>
      <span className="rounded-full bg-accent/12 px-2 py-0.5 font-mono text-micro text-accent">
        {parsed.intent.replace("_", " ")}
      </span>
      {slots.map(([k, v]) => (
        <span
          key={k}
          className="rounded-full bg-surface-inset2 px-2 py-0.5 font-mono text-micro text-ink-dim"
        >
          {SLOT_LABEL[k] ?? k.replace(/_/g, " ")} {String(v)}
        </span>
      ))}
      <span className="ml-auto font-mono text-micro text-ink-fainter">via {parsed.parser}</span>
    </div>
  );
}

/** Shown when the answer was resolved against the previous question. Silent
 *  context-carrying is the same failure as a silent misparse: the user needs to
 *  know the engine answered "…for Silverstone, at 35°C" and not just "35°C". */
function MergedNote() {
  return (
    <div className="mt-2 flex items-center gap-1.5 font-mono text-micro text-ink-faint">
      <span className="h-[5px] w-[5px] shrink-0 rounded-full bg-accent" />
      read as a refinement of your previous question
    </div>
  );
}

// --- the numbers behind the sentence ----------------------------------------

/** One compact table or metric row per intent. The full treatment of each of
 *  these lives in its own view — this is the evidence for the sentence, not a
 *  replacement for Strategy or Standings. */
function AnswerData({ intent, data }: { intent: string; data: Record<string, unknown> }) {
  if (intent === "recommend") return <RecommendData d={data as unknown as RecommendResp} />;
  if (intent === "undercut") return <UndercutData d={data as unknown as UndercutResp} />;
  if (intent === "degradation") return <DegradationData d={data as unknown as DegradationResp} />;
  if (intent === "standings") return <StandingsData d={data as unknown as StandingsResp} />;
  if (intent === "next_race") return <UpcomingData d={data as unknown as UpcomingResp} />;
  if (intent === "race_result") return <RaceResultData d={data as unknown as RaceCardResp} />;
  return null;
}

function Frame({ children }: { children: React.ReactNode }) {
  return <div className="mt-3 rounded-lg border border-line bg-surface-inset/40 p-1">{children}</div>;
}

function RecommendData({ d }: { d: RecommendResp }) {
  const cols: Column<ShortlistRow>[] = [
    { key: "rank", header: "#", render: (r) => r.rank, align: "right" },
    { key: "plan", header: "Plan", render: (r) => fmtPlan(r.compounds, r.pit_laps) },
    { key: "mean", header: "Mean", render: (r) => clock(r.mean_s), align: "right" },
    {
      key: "beats",
      header: "Confidence",
      render: (r) => (
        <span className={r.rank === 1 ? "text-accent" : "text-ink-muted"}>
          {beatsPick(r.rank, r.win_prob_vs_best)}
        </span>
      ),
      align: "right",
    },
  ];
  return (
    <Frame>
      <DataTable
        columns={cols}
        rows={d.shortlist.slice(0, 3)}
        getKey={(r) => r.rank}
        highlightFirst
        label={`Strategy shortlist for ${d.track}`}
      />
    </Frame>
  );
}

function UndercutData({ d }: { d: UndercutResp }) {
  return (
    <div className="mt-3 grid grid-cols-3 gap-px overflow-hidden rounded-lg border border-line bg-line">
      <Metric
        variant="cell"
        label="Gain"
        value={`${d.undercut_gain_s >= 0 ? "+" : ""}${d.undercut_gain_s.toFixed(1)}s`}
        accent={d.undercut_works}
      />
      <Metric variant="cell" label="Pit now" value={pct(d.undercut.p_ahead)} sub="ends up ahead" />
      <Metric variant="cell" label="Stay out" value={pct(d.cover.p_ahead)} sub="ends up ahead" />
    </div>
  );
}

function DegradationData({ d }: { d: DegradationResp }) {
  const rows = Object.entries(d.compounds).map(([compound, c]) => ({ compound, ...c }));
  const cols: Column<(typeof rows)[number]>[] = [
    {
      key: "compound",
      header: "Compound",
      render: (r) => (
        <span className="inline-flex items-center gap-1.5">
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ background: compoundColor(r.compound) }}
          />
          {r.compound}
        </span>
      ),
    },
    {
      key: "slope",
      header: "Per lap",
      render: (r) => (r.slope == null ? "—" : `${r.slope.toFixed(3)} s`),
      align: "right",
    },
    { key: "max", header: "Modelled to", render: (r) => `${r.max_age} laps`, align: "right" },
  ];
  return (
    <Frame>
      <DataTable
        columns={cols}
        rows={rows}
        getKey={(r) => r.compound}
        label={`Tyre degradation at ${d.track}`}
      />
    </Frame>
  );
}

function StandingsData({ d }: { d: StandingsResp }) {
  const cols: Column<DriverStanding>[] = [
    { key: "pos", header: "#", render: (r) => r.pos, align: "right" },
    { key: "driver", header: "Driver", render: (r) => r.driver },
    { key: "team", header: "Team", render: (r) => <span className="text-ink-muted">{r.team}</span> },
    { key: "pts", header: "Points", render: (r) => r.points.toFixed(0), align: "right" },
  ];
  return (
    <Frame>
      <DataTable
        columns={cols}
        rows={d.drivers.slice(0, 5)}
        getKey={(r) => r.driver}
        highlightFirst
        label={`${d.season} drivers' championship, top five`}
      />
    </Frame>
  );
}

function UpcomingData({ d }: { d: UpcomingResp }) {
  const cols: Column<UpcomingPred>[] = [
    { key: "driver", header: "Driver", render: (r) => r.driver },
    { key: "grid", header: "Grid", render: (r) => `P${r.grid}`, align: "right" },
    {
      key: "prob",
      header: "Podium",
      render: (r) => <span className="text-accent">{pct(r.podium_prob)}</span>,
      align: "right",
    },
  ];
  return (
    <Frame>
      <DataTable
        columns={cols}
        rows={d.predictions.slice(0, 3)}
        getKey={(r) => r.driver}
        highlightFirst
        label={`Podium prediction for round ${d.next_round}`}
      />
    </Frame>
  );
}

function RaceResultData({ d }: { d: RaceCardResp }) {
  if (!d.actual_podium?.length) return null;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      {d.actual_podium.slice(0, 3).map((driver, i) => (
        <span
          key={driver}
          className={`rounded-md px-2.5 py-1 font-mono text-data ${
            i === 0 ? "bg-accent/12 text-accent" : "bg-surface-inset2 text-ink-dim"
          }`}
        >
          P{i + 1} {driver}
        </span>
      ))}
      {d.prediction && (
        <span className="font-mono text-mini text-ink-faint">
          model had {d.prediction.hit_at_3}/3 before the race
        </span>
      )}
    </div>
  );
}
