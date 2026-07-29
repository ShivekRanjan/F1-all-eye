import { useState, type RefObject } from "react";
import { api } from "../api/client";
import { Badge, Card, CardSkeleton, ErrorNote, SectionTitle, Skeleton } from "../components/ui";
import { AnimatedNumber } from "../components/AnimatedNumber";
import { DriverCutout, DriverName, DriverTag } from "../components/Driver";
import { ChequeredFlagIcon, PodiumIcon } from "../components/NavIcons";
import { TrackOutline } from "../components/TrackOutline";
import { driverCutoutUrl } from "../lib/driverCutouts";
import { pct, teamColor, timeAgo } from "../lib/format";
import { countdown, fmtSession, useNow } from "../lib/time";
import { useAsync } from "../lib/useAsync";
import { useLastVisit } from "../lib/useLastVisit";
import { useParallax } from "../lib/useParallax";
import { useSettings } from "../lib/useSettings";
import type { CalendarResp, GridSource, NewsResp, StandingsResp, UpcomingResp } from "../api/types";

/** Secondary "go to the full section" links. Deliberately not accent-coloured:
 *  gold is reserved for what the *models* say — podium probabilities, the
 *  recommended strategy, title odds — so that seeing gold means "this is a
 *  claim the engine is making", not "this is a link". */
const SECONDARY_LINK =
  "font-mono text-[11px] text-ink-dim transition hover:text-ink-soft";

/** The OS home: what's next, what the model expects, where the title stands,
 *  and what the paddock is talking about — each block deep-links to its section. */
export default function HomeView() {
  return (
    <div className="space-y-5">
      <p className="max-w-3xl text-sm text-ink-muted">
        One screen for the season: the next race with the model's podium call, the live title race,
        and the latest headlines. Everything links into its full section — start anywhere.
      </p>
      <NextRaceHero />
      <div className="grid gap-5 lg:grid-cols-[1.25fr_1fr]">
        <TitleRace />
        <Headlines />
      </div>
      <ExploreStrip />
    </div>
  );
}

// --- Next race + the model's call --------------------------------------------
function NextRaceHero() {
  const cal = useAsync(async () => {
    const seasons = await api.allSeasons();
    const latest = seasons.seasons.at(-1);
    return latest ? api.calendar(latest) : null;
  }, []);
  const up = useAsync(() => api.predictUpcoming(), []);
  // Hooks must run unconditionally — before the early returns below.
  const { containerRef, targetRef } = useParallax<HTMLDivElement, HTMLDivElement>(7);
  // Race-day mode is only true for ~2h of a race week, so without a way to ask
  // for it nobody would ever see it. Deliberately not persisted — a preview
  // should not outlive the visit and start looking like the real thing.
  const [preview, setPreview] = useState(false);

  if (cal.error) return <ErrorNote error={cal.error} />;
  if (!cal.data) return <CardSkeleton label="Finding the next race…" height={200} />;

  const round = cal.data.rounds.find((r) => r.round === cal.data!.next_round);
  const next = cal.data.next_session;
  if (!round || !next) return <SeasonOver cal={cal.data} />;

  return (
    <Card className="relative overflow-hidden border-l-2 border-l-accent">
      <div ref={containerRef} className="relative">
        <div className="pointer-events-none absolute inset-y-0 left-0 w-1/3 animate-sweep bg-gradient-to-r from-transparent via-accent/[0.06] to-transparent" />
        <Hero
          round={round}
          next={next}
          up={up.data ?? null}
          upErr={!!up.error}
          outlineRef={targetRef}
          preview={preview}
          onPreview={setPreview}
        />
      </div>
    </Card>
  );
}

function Hero({
  round,
  next,
  up,
  upErr,
  outlineRef,
  preview,
  onPreview,
}: {
  round: NonNullable<CalendarResp["rounds"][number]>;
  next: NonNullable<CalendarResp["next_session"]>;
  up: UpcomingResp | null;
  upErr: boolean;
  outlineRef: RefObject<HTMLDivElement>;
  preview: boolean;
  onPreview: (v: boolean) => void;
}) {
  const now = useNow();
  const [settings] = useSettings();
  const hour12 = settings.timeFormat === "12h";
  const podium = up && up.next_round === round.round ? up.predictions.slice(0, 3) : null;

  // Race-day mode: as a session comes inside ~2h (or is under way), the hero
  // drops its week-out calm and gets urgent — pulsing ribbon, enlarged
  // countdown, "final call" language. Purely presentational; same data.
  const msToNext = new Date(next.date).getTime() - now;
  const live = msToNext <= 0 && !preview;
  const soon = msToNext > 0 && msToNext <= 2 * 3600 * 1000;
  const raceMode = live || soon || preview;
  const isRace = /race/i.test(next.name);
  // Real race day vs. a preview of it: the countdown below stays truthful in
  // both, so a previewed ribbon sits next to an honest "3d 5h" and can't be
  // mistaken for the session actually being imminent.
  const previewOnly = preview && !live && !soon;

  return (
    <>
      {raceMode && (
        <div className="flex items-center gap-2 border-b border-accent/30 bg-accent/[0.08] px-4 py-1.5">
          <span className="h-2 w-2 animate-f1pulse rounded-full bg-accent" />
          <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-accent">
            {live
              ? `${next.name} under way`
              : isRace
                ? "Lights out soon"
                : `${next.name} starts soon`}
          </span>
          {previewOnly && (
            <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-faint">
              · preview
            </span>
          )}
        </div>
      )}
      <div className="p-4 pb-0">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            {/* Cursor-reactive parallax — the track drifts subtly with the
                mouse, the hero's one intentionally "alive" element. */}
            <div ref={outlineRef} className="mt-1 transition-transform duration-150 ease-out">
              <TrackOutline track={round.event_name} size={48} className="text-accent" />
            </div>
            <div>
              <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-ink-faint">
                Next race · Round {round.round}
              </div>
              <div className="mt-1 flex items-center gap-2">
                {/* The race is the subject of this card, so it gets the largest
                    and heaviest type. It previously sat at 24px/700 under a
                    30px countdown — size said "look at the clock" while weight
                    said "look at the race", and three weeks out the clock is
                    the least actionable thing on the page. */}
                <span className="text-3xl font-700 leading-tight text-ink">{round.event_name}</span>
                {round.format?.includes("sprint") && <Badge tone="amber">Sprint</Badge>}
              </div>
              <div className="text-sm text-ink-muted">
                {round.location}, {round.country}
              </div>
            </div>
          </div>
          <div className="text-right">
            <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-ink-faint">
              {next.name} in
            </div>
            {/* Supporting by default, promoted on race day. Gold is reserved
                for the model's own output, so a countdown — plain fact, not a
                prediction — only earns the accent once it's genuinely urgent.
                That makes race-day mode read as an event rather than a
                slightly larger version of the same card. */}
            <div
              className={`nums font-mono ${
                raceMode
                  ? "animate-f1pulse text-4xl font-700 text-accent"
                  : "text-xl text-ink-soft"
              }`}
            >
              {countdown(next.date, now)}
            </div>
            <div className="font-mono text-[11px] text-ink-muted">{fmtSession(next.date, hour12)}</div>
          </div>
        </div>

        <div className="mb-2 mt-5 flex items-center justify-between">
          <span className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.12em] text-ink-faint">
              {raceMode && isRace ? (
                <ChequeredFlagIcon width={13} height={13} className="text-accent" />
              ) : (
                <PodiumIcon width={13} height={13} />
              )}
              {raceMode && isRace ? "Final podium call" : "Predicted podium"}
            </span>
            {podium && <GridSourceChip source={up!.grid_source} />}
          </span>
          <span className="flex items-center gap-3">
            {/* Only offered when it isn't genuinely race day — during the real
                thing there is nothing to preview. */}
            {!live && !soon && (
              <button
                onClick={() => onPreview(!preview)}
                aria-pressed={preview}
                title={
                  preview
                    ? "Back to the normal next-race card"
                    : "See how this card looks in the last 2 hours before a session"
                }
                className={`font-mono text-[11px] transition hover:opacity-80 ${
                  preview ? "text-accent" : "text-ink-faint hover:text-ink-soft"
                }`}
              >
                {preview ? "✕ exit preview" : "▸ preview race day"}
              </button>
            )}
            {/* Secondary navigation, so it reads as such. These were gold —
                four of them, at the same weight as the model's own output,
                which is what left the page with seven equally-loud exits and
                no primary one. */}
            <a href="#/outcome" className={SECONDARY_LINK}>
              tune the grid →
            </a>
            <a href="#/calendar" className={SECONDARY_LINK}>
              full schedule →
            </a>
          </span>
        </div>
        {(!podium && !upErr) && <Skeleton className="h-24 w-full" />}
      </div>
      {/* Podium riser boxes sit flush against the card's bottom edge (no
          padding below them, by construction — not a negative-margin hack). */}
      {podium ? (
        <div className="px-4">
          <PodiumBlocks podium={podium} />
        </div>
      ) : upErr ? (
        <div className="px-4 pb-4">
          <span className="text-sm text-ink-muted">prediction unavailable</span>
        </div>
      ) : null}
    </>
  );
}

/** Says what the call is actually standing on. Once qualifying has run the
 *  engine feeds the real starting order in by itself, and that's a stronger
 *  claim than a projection off season-average qualifying form — so the two
 *  don't get to look identical. */
function GridSourceChip({ source }: { source: GridSource }) {
  const label =
    source === "qualifying"
      ? "off the real grid"
      : source === "custom"
        ? "your grid"
        : "projected from form";
  const title =
    source === "qualifying"
      ? "Start positions are this weekend's actual qualifying classification (before any grid penalties)."
      : source === "custom"
        ? "Start positions you set by hand in the Outcome view."
        : "Qualifying hasn't run yet — start positions are each driver's season-average qualifying position.";
  return (
    <span
      title={title}
      className={`rounded-full border px-2 py-0.5 font-mono text-[10px] ${
        source === "form"
          ? "border-line-ctl text-ink-faint"
          : "border-accent/40 bg-accent/10 text-accent"
      }`}
    >
      {label}
    </span>
  );
}

/** P2 / P1 / P3 ceremony blocks — P1 centered and tallest, matching a real podium.
 *  Driver info sits in its own uniform block above the riser (not squeezed
 *  inside it), so avatar/name/percentage stay pixel-level across all three
 *  regardless of how tall each riser is. */
function PodiumBlocks({
  podium,
}: {
  podium: NonNullable<UpcomingResp["predictions"]>;
}) {
  const [p1, p2, p3] = podium;
  const order = [
    { row: p2, place: 2, riser: "h-12", cutoutH: 80, tone: "border-line-card bg-surface-inset" },
    { row: p1, place: 1, riser: "h-20", cutoutH: 105, tone: "border-accent/50 bg-accent/[0.07]" },
    { row: p3, place: 3, riser: "h-9", cutoutH: 68, tone: "border-line-card bg-surface-inset" },
  ] as const;
  return (
    <div className="flex items-end gap-2">
      {order.map(({ row, place, riser, cutoutH, tone }, i) =>
        row ? (
          <div
            key={row.driver}
            className="animate-rise flex flex-1 flex-col items-center"
            style={{ animationDelay: `${i * 90}ms` }}
          >
            {/* A true cutout (transparent-bg photo) when we have one for this
                driver — bleeds down into the info row below like a broadcast
                podium graphic. When present, the small circular avatar below
                would just be the same face twice, so swap it for name-only. */}
            <DriverCutout
              code={row.driver}
              height={cutoutH}
              className="-mb-1 drop-shadow-[0_6px_10px_rgba(0,0,0,0.45)]"
            />
            <div className="flex flex-col items-center pb-2.5">
              {driverCutoutUrl(row.driver) ? (
                <DriverName code={row.driver} className="font-700 text-ink" />
              ) : (
                <DriverTag code={row.driver} size={place === 1 ? 26 : 22} />
              )}
            </div>
            <div
              className={`flex w-full flex-col items-center justify-end rounded-t-lg border border-b-0 pb-1.5 leading-tight ${riser} ${tone}`}
            >
              <AnimatedNumber
                value={row.podium_prob}
                format={pct}
                className={`nums font-mono text-[11px] ${place === 1 ? "text-accent" : "text-ink-muted"}`}
              />
              <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-faint">
                P{place}
              </span>
            </div>
          </div>
        ) : null,
      )}
    </div>
  );
}

function SeasonOver({ cal }: { cal: CalendarResp }) {
  return (
    <Card className="p-4">
      <SectionTitle>Season complete</SectionTitle>
      <p className="text-sm text-ink-muted">
        All {cal.rounds.length} rounds of {cal.season} have run —{" "}
        <a href="#/standings" className="text-accent">see the final standings</a> or{" "}
        <a href="#/racehub" className="text-accent">relive any race in the Race Hub</a>.
      </p>
    </Card>
  );
}

// --- Title race snapshot ------------------------------------------------------
function TitleRace() {
  const s = useAsync(() => api.standings(), []);
  if (s.error) return <ErrorNote error={s.error} />;
  if (!s.data) return <CardSkeleton label="Tallying the championship…" height={280} />;
  return <TitleRaceBody data={s.data} />;
}

function TitleRaceBody({ data }: { data: StandingsResp }) {
  const [settings] = useSettings();
  const top = data.drivers.slice(0, 8);
  const maxPts = Math.max(1, ...top.map((d) => d.points));
  return (
    <Card className="p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <SectionTitle>
          Title race — {data.season}{" "}
          {data.ongoing && (
            <Badge tone="red">
              {data.races_done} of {data.total_races} races
            </Badge>
          )}
        </SectionTitle>
        <a href="#/standings" className={SECONDARY_LINK}>
          full standings →
        </a>
      </div>
      <div className="space-y-2">
        {top.map((d) => (
          <div
            key={d.driver}
            className={`flex items-center gap-3 rounded-md px-1.5 -mx-1.5 ${
              d.driver === settings.favoriteDriver ? "bg-accent/[0.06] ring-1 ring-inset ring-accent/30" : ""
            }`}
          >
            <span className="w-5 text-right font-mono text-[12px] text-ink-faint">{d.pos}</span>
            <span className="inline-block h-3.5 w-1 rounded-sm" style={{ background: teamColor(d.team) }} />
            <DriverTag code={d.driver} team={d.team} size={22} />
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-inset">
              <div
                className="h-full rounded-full bg-accent/70"
                style={{ width: `${(d.points / maxPts) * 100}%` }}
              />
            </div>
            <AnimatedNumber value={d.points} className="nums w-12 text-right font-mono text-[12px] text-ink" />
            {data.ongoing && (
              <span className="nums w-12 text-right font-mono text-[12px] text-accent">
                {d.win_prob != null ? <AnimatedNumber value={d.win_prob} format={pct} /> : "—"}
              </span>
            )}
          </div>
        ))}
      </div>
      {data.ongoing && (
        <p className="mt-2 text-right font-mono text-[11px] text-ink-faint">points · title odds</p>
      )}
    </Card>
  );
}

// --- Headlines ----------------------------------------------------------------
function Headlines() {
  const n = useAsync(() => api.news(6), []);
  if (n.error) return <ErrorNote error={n.error} />;
  if (!n.data) return <CardSkeleton label="Fetching headlines…" height={280} />;
  return <HeadlinesBody data={n.data} />;
}

function HeadlinesBody({ data }: { data: NewsResp }) {
  const lastVisit = useLastVisit();
  if (!data.items.length) return null;
  return (
    <Card className="p-4">
      <div className="mb-2 flex items-baseline justify-between">
        <SectionTitle>Paddock news</SectionTitle>
        <a href="#/news" className={SECONDARY_LINK}>
          all headlines →
        </a>
      </div>
      <div className="divide-y divide-line/60">
        {data.items.slice(0, 5).map((it) => (
          <a
            key={it.link}
            href={it.link}
            target="_blank"
            rel="noreferrer noopener"
            className="group block py-2"
          >
            <div className="flex items-center gap-2 font-mono text-[11px]">
              <span className="text-accent">{it.source}</span>
              <span className="text-ink-faint">{timeAgo(it.ts)}</span>
              {!!lastVisit && !!it.ts && it.ts > lastVisit && (
                <span className="h-1.5 w-1.5 rounded-full bg-soft" title="new since your last visit" />
              )}
            </div>
            <div className="text-sm font-600 text-ink group-hover:text-accent">{it.title}</div>
          </a>
        ))}
      </div>
    </Card>
  );
}

// --- Explore the toolkit --------------------------------------------------------
const TOOLS = [
  {
    href: "#/racehub",
    title: "Race Hub",
    blurb: "Any race: prediction vs result, strategy call, tyre curves, pace trace.",
  },
  {
    href: "#/live",
    title: "Live replay",
    blurb: "Replay lap by lap; the engine re-optimises from every state.",
  },
] as const;

/** One primary action, then the rest.
 *
 *  Home used to offer seven exits at identical weight — a hub with no opinion.
 *  The project does have one: the README's first line is "not who will win —
 *  what should the team do", and that is the strategy optimiser. So it gets a
 *  filled accent card at full width and the others sit beneath it as secondary
 *  outlines. Nothing was removed; the ordering just now says something. */
function ExploreStrip() {
  return (
    <div className="space-y-3">
      <a
        href="#/strategy"
        className="group flex items-center justify-between gap-4 rounded-xl2 border border-accent/50 bg-accent/[0.07] p-4 shadow-card transition hover:bg-accent/[0.12]"
      >
        <span>
          <span className="block font-700 text-accent">Strategy optimiser →</span>
          <span className="mt-0.5 block text-sm text-ink-soft">
            The question the engine exists to answer: when to stop and on what, with the
            honest spread. Monte-Carlo over 1,000+ pit plans.
          </span>
        </span>
        <span className="hidden shrink-0 font-mono text-[10px] uppercase tracking-[0.16em] text-accent/70 sm:block">
          start here
        </span>
      </a>
      <div className="grid gap-3 sm:grid-cols-2">
        {TOOLS.map((t) => (
          <a
            key={t.href}
            href={t.href}
            className="group rounded-xl2 border border-line bg-carbon-800 p-4 shadow-card transition hover:border-line-hover"
          >
            <div className="mb-1 font-700 text-ink">{t.title} →</div>
            <div className="text-sm text-ink-muted">{t.blurb}</div>
          </a>
        ))}
      </div>
    </div>
  );
}
