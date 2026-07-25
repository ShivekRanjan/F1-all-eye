import { useEffect, useState } from "react";
import { api } from "../api/client";
import { Badge, Card, CardSkeleton, ErrorNote, SectionTitle } from "../components/ui";
import { PodiumIcon } from "../components/NavIcons";
import { pct } from "../lib/format";
import { pickSeason } from "../lib/season";
import { countdown, fmtSession, useNow } from "../lib/time";
import { useAsync } from "../lib/useAsync";
import { useSettings } from "../lib/useSettings";
import type { CalendarRound, CalendarResp, CalendarSession } from "../api/types";
import { ViewIntro } from "./common";

const fmtDay = (iso: string | null) =>
  iso ? new Date(iso + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "";

export default function CalendarView() {
  const [settings] = useSettings();
  const seasons = useAsync(() => api.allSeasons(), []);
  const [season, setSeason] = useState<number | null>(null);
  useEffect(() => {
    if (seasons.data?.seasons?.length) {
      setSeason((prev) => prev ?? pickSeason(seasons.data!.seasons, settings.defaultSeason));
    }
  }, [seasons.data]);

  const cal = useAsync(
    () => (season == null ? Promise.resolve(null) : api.calendar(season)),
    [season],
  );

  return (
    <div className="space-y-5">
      <ViewIntro>
        The full season calendar — every round, circuit and session time, with the next race counted
        down live. Real-time timing streams only while a session is running; between sessions, the{" "}
        <strong>Live Race</strong> tab replays any completed race lap by lap.
      </ViewIntro>

      {(seasons.data?.seasons?.length ?? 0) > 1 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="mr-1 font-mono text-[11px] uppercase tracking-[0.12em] text-ink-faint">Season</span>
          {seasons.data!.seasons.slice().reverse().map((y) => (
            <button
              key={y}
              onClick={() => setSeason(y)}
              className={`rounded-md border px-3 py-1.5 font-mono text-[12px] transition ${
                y === season
                  ? "border-accent/60 bg-accent/10 text-accent"
                  : "border-line-ctl text-ink-dim hover:border-line-hover hover:text-ink-soft"
              }`}
            >
              {y}
            </button>
          ))}
        </div>
      )}

      {cal.error && <ErrorNote error={cal.error} />}
      {season != null && !cal.data && !cal.error && <CardSkeleton label="Loading the calendar…" height={320} />}
      {cal.data && <Body cal={cal.data} />}
    </div>
  );
}

function Body({ cal }: { cal: CalendarResp }) {
  const nextRound = cal.rounds.find((r) => r.round === cal.next_round) ?? null;
  return (
    <>
      {nextRound && cal.next_session && <NextRaceCard round={nextRound} nextSessionIso={cal.next_session.date} nextSessionName={cal.next_session.name} />}
      <Card className="p-4">
        <SectionTitle>
          {cal.season} calendar · {cal.rounds.filter((r) => r.done).length}/{cal.rounds.length} run
        </SectionTitle>
        <div className="divide-y divide-line">
          {cal.rounds.map((r) => (
            <RoundRow key={r.round} r={r} isNext={r.round === cal.next_round} />
          ))}
        </div>
      </Card>
    </>
  );
}

function NextRaceCard({
  round,
  nextSessionIso,
  nextSessionName,
}: {
  round: CalendarRound;
  nextSessionIso: string;
  nextSessionName: string;
}) {
  const now = useNow(true);
  const [settings] = useSettings();
  const hour12 = settings.timeFormat === "12h";
  const isSprint = round.format?.includes("sprint");
  return (
    <Card className="border-l-2 border-l-accent p-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-ink-faint">
            Next up · Round {round.round}
          </div>
          <div className="mt-1 flex items-center gap-2">
            <span className="text-2xl font-700 text-ink">{round.event_name}</span>
            {isSprint && <Badge tone="amber">Sprint</Badge>}
          </div>
          <div className="text-sm text-ink-muted">
            {round.location}, {round.country}
          </div>
        </div>
        <div className="text-right">
          <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-ink-faint">
            {nextSessionName} in
          </div>
          <div className="nums font-mono text-3xl text-accent">{countdown(nextSessionIso, now)}</div>
          <div className="font-mono text-[11px] text-ink-muted">{fmtSession(nextSessionIso, hour12)}</div>
        </div>
      </div>

      <SessionTimeline sessions={round.sessions} now={now} />

      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
        {round.sessions.map((s) => {
          const upcoming = new Date(s.date).getTime() > now;
          return (
            <div
              key={s.name}
              className={`rounded-md border px-3 py-2 ${
                upcoming ? "border-line-card bg-surface-inset" : "border-line bg-transparent opacity-60"
              }`}
            >
              <div className="font-mono text-[11px] uppercase tracking-[0.1em] text-ink-faint">{s.name}</div>
              <div className="text-sm text-ink">{fmtSession(s.date, hour12)}</div>
              {upcoming && <div className="font-mono text-[11px] text-accent">in {countdown(s.date, now)}</div>}
            </div>
          );
        })}
      </div>

      <PredictedPodium round={round.round} />
    </Card>
  );
}

/** FP1 -> Race as a broadcast-style timeline instead of just a grid of
 *  cards — a moving "now" marker gives the weekend a sense of progress,
 *  not just a list of times. Sessions sit at EQUAL intervals (index-based),
 *  not spaced proportionally to actual elapsed time — real gaps between
 *  sessions vary wildly (3.5h practice-to-practice vs. ~23h to race day),
 *  so proportional spacing clustered sessions together and read as broken.
 *  The "now" marker still interpolates using real time, just within
 *  whichever equal-width segment "now" currently falls in. */
function SessionTimeline({ sessions, now }: { sessions: CalendarSession[]; now: number }) {
  if (sessions.length < 2) return null;
  const times = sessions.map((s) => new Date(s.date).getTime());
  const n = sessions.length;

  // The session cards below are an n-column CSS grid — each card is
  // centered within its own 1/n slice, not spread edge-to-edge. Dots have
  // to land on those same centers ((i+0.5)/n) or the timeline visibly
  // drifts out of alignment with the cards under it.
  const posForIndex = (x: number) => ((x + 0.5) / n) * 100;

  let nowPct: number;
  if (now <= times[0]) {
    nowPct = posForIndex(0);
  } else if (now >= times[n - 1]) {
    nowPct = posForIndex(n - 1);
  } else {
    const i = times.findIndex((t, idx) => idx < n - 1 && now >= t && now < times[idx + 1]);
    const segStart = times[i];
    const segEnd = times[i + 1];
    const withinSeg = (now - segStart) / Math.max(1, segEnd - segStart);
    nowPct = posForIndex(i + withinSeg);
  }
  const trackStart = posForIndex(0);
  const trackEnd = posForIndex(n - 1);

  return (
    <div className="relative mx-1 mt-5 mb-6 h-2">
      <div
        className="absolute top-1/2 h-[2px] -translate-y-1/2 rounded-full bg-surface-inset2"
        style={{ left: `${trackStart}%`, right: `${100 - trackEnd}%` }}
      />
      <div
        className="absolute top-1/2 h-[2px] -translate-y-1/2 rounded-full bg-accent/60 transition-[width] duration-500"
        style={{ left: `${trackStart}%`, width: `${Math.max(0, nowPct - trackStart)}%` }}
      />
      {sessions.map((s, i) => {
        const leftPct = posForIndex(i);
        const passed = times[i] <= now;
        return (
          <div
            key={s.name}
            className="absolute top-1/2 flex -translate-x-1/2 -translate-y-1/2 flex-col items-center"
            style={{ left: `${leftPct}%` }}
          >
            <span
              className={`block h-2.5 w-2.5 rounded-full border-2 ${
                passed ? "border-accent bg-accent" : "border-line-hover bg-surface-page"
              }`}
            />
            <span className="absolute top-4 whitespace-nowrap font-mono text-[10px] uppercase tracking-[0.1em] text-ink-faint">
              {s.name}
            </span>
          </div>
        );
      })}
      {nowPct > trackStart + 0.5 && nowPct < trackEnd - 0.5 && (
        <div
          className="pointer-events-none absolute top-1/2 -translate-x-1/2 -translate-y-1/2"
          style={{ left: `${nowPct}%` }}
        >
          <span className="block h-3.5 w-3.5 animate-f1pulse rounded-full bg-accent shadow-glow" />
        </div>
      )}
    </div>
  );
}

/** The model's podium call for the next race, right where people look for it.
 *  Uses the same /predict_upcoming the Outcome tab serves; hidden if the
 *  prediction's round doesn't match this calendar round (data lag) or errors. */
function PredictedPodium({ round }: { round: number }) {
  const up = useAsync(() => api.predictUpcoming(), []);
  if (up.error || (up.data && up.data.next_round !== round)) return null;
  if (!up.data) return null;
  const podium = up.data.predictions.slice(0, 3);
  return (
    <div className="mt-4 border-t border-line pt-3">
      <div className="mb-2 flex items-baseline justify-between">
        <span className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.12em] text-ink-faint">
          <PodiumIcon width={13} height={13} />
          Model's predicted podium
        </span>
        <a href="#/outcome" className="font-mono text-[11px] text-accent transition hover:opacity-80">
          tune the grid in Outcome →
        </a>
      </div>
      <div className="flex flex-wrap gap-2">
        {podium.map((p, i) => (
          <span key={p.driver} className="rounded-lg border border-line-card bg-surface-inset px-3 py-1.5">
            <span className="mr-1.5 font-mono text-[11px] text-ink-faint">P{i + 1}</span>
            <span className="font-700 text-ink">{p.driver}</span>{" "}
            <span className="nums font-mono text-[12px] text-accent">{pct(p.podium_prob)}</span>
          </span>
        ))}
      </div>
      <p className="mt-1.5 text-[11px] text-ink-muted">
        From current form; the grid defaults to qualifying form until the real grid is set.
      </p>
    </div>
  );
}

function RoundRow({ r, isNext }: { r: CalendarRound; isNext: boolean }) {
  return (
    <div className={`flex items-center gap-3 py-2.5 ${r.done ? "opacity-55" : ""}`}>
      <span className="w-7 text-center font-mono text-[12px] text-ink-faint">{r.round}</span>
      <span className="w-14 font-mono text-[12px] text-ink-muted">{fmtDay(r.event_date)}</span>
      <span className={`font-600 ${isNext ? "text-accent" : "text-ink"}`}>{r.event_name}</span>
      <span className="text-xs text-ink-muted">{r.country}</span>
      {r.format?.includes("sprint") && <Badge tone="amber">Sprint</Badge>}
      <span className="ml-auto">
        {r.done ? (
          <span className="font-mono text-[11px] text-ink-faint">✓ done</span>
        ) : isNext ? (
          <Badge tone="red">next</Badge>
        ) : (
          <span className="font-mono text-[11px] text-ink-faint">upcoming</span>
        )}
      </span>
    </div>
  );
}
