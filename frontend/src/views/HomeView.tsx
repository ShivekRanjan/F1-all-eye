import type { RefObject } from "react";
import { api } from "../api/client";
import { Badge, Card, CardSkeleton, ErrorNote, SectionTitle, Skeleton } from "../components/ui";
import { AnimatedNumber } from "../components/AnimatedNumber";
import { DriverCutout, DriverName, DriverTag } from "../components/Driver";
import { TrackOutline } from "../components/TrackOutline";
import { driverCutoutUrl } from "../lib/driverCutouts";
import { pct, teamColor, timeAgo } from "../lib/format";
import { countdown, fmtSession, useNow } from "../lib/time";
import { useAsync } from "../lib/useAsync";
import { useLastVisit } from "../lib/useLastVisit";
import { useParallax } from "../lib/useParallax";
import { useSettings } from "../lib/useSettings";
import type { CalendarResp, NewsResp, StandingsResp, UpcomingResp } from "../api/types";

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

  if (cal.error) return <ErrorNote error={cal.error} />;
  if (!cal.data) return <CardSkeleton label="Finding the next race…" height={200} />;

  const round = cal.data.rounds.find((r) => r.round === cal.data!.next_round);
  const next = cal.data.next_session;
  if (!round || !next) return <SeasonOver cal={cal.data} />;

  return (
    <Card className="relative overflow-hidden border-l-2 border-l-accent">
      <div ref={containerRef} className="relative">
        <div className="pointer-events-none absolute inset-y-0 left-0 w-1/3 animate-sweep bg-gradient-to-r from-transparent via-accent/[0.06] to-transparent" />
        <Hero round={round} next={next} up={up.data ?? null} upErr={!!up.error} outlineRef={targetRef} />
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
}: {
  round: NonNullable<CalendarResp["rounds"][number]>;
  next: NonNullable<CalendarResp["next_session"]>;
  up: UpcomingResp | null;
  upErr: boolean;
  outlineRef: RefObject<HTMLDivElement>;
}) {
  const now = useNow();
  const [settings] = useSettings();
  const hour12 = settings.timeFormat === "12h";
  const podium = up && up.next_round === round.round ? up.predictions.slice(0, 3) : null;
  return (
    <>
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
                <span className="text-2xl font-700 text-ink">{round.event_name}</span>
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
            <div className="nums font-mono text-3xl text-accent">{countdown(next.date, now)}</div>
            <div className="font-mono text-[11px] text-ink-muted">{fmtSession(next.date, hour12)}</div>
          </div>
        </div>

        <div className="mb-2 mt-5 flex items-center justify-between">
          <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-ink-faint">
            🔮 Predicted podium
          </span>
          <span className="flex gap-3">
            <a href="#/outcome" className="font-mono text-[11px] text-accent hover:opacity-80">
              tune the grid →
            </a>
            <a href="#/calendar" className="font-mono text-[11px] text-accent hover:opacity-80">
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
        <a href="#/standings" className="font-mono text-[11px] text-accent hover:opacity-80">
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
        <a href="#/news" className="font-mono text-[11px] text-accent hover:opacity-80">
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
    href: "#/strategy",
    title: "Strategy optimiser",
    blurb: "Monte-Carlo search over 1,000+ pit plans — with a track-temp control.",
  },
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

function ExploreStrip() {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {TOOLS.map((t) => (
        <a
          key={t.href}
          href={t.href}
          className="group rounded-xl2 border border-line bg-carbon-800 p-4 shadow-card transition hover:border-accent/40"
        >
          <div className="mb-1 font-700 text-ink group-hover:text-accent">{t.title} →</div>
          <div className="text-sm text-ink-muted">{t.blurb}</div>
        </a>
      ))}
    </div>
  );
}
