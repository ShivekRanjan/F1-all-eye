import { useEffect, useState } from "react";
import { api, checkHealth } from "../api/client";
import { Callout, Card, SectionTitle } from "../components/ui";
import { DriverAvatar } from "../components/Driver";
import { useAsync } from "../lib/useAsync";
import { type Accent, type Density, type TimeFormat, resetSettings, useSettings } from "../lib/useSettings";
import { useDrivers } from "../lib/useDrivers";
import { ViewIntro } from "./common";

const ACCENTS: { id: Accent; hex: string; label: string }[] = [
  { id: "gold", hex: "#d4af37", label: "Podium gold" },
  { id: "cyan", hex: "#22e0ff", label: "Cool cyan" },
  { id: "violet", hex: "#a855f7", label: "Night violet" },
];

/** V2 Settings — the app's one page of personal preference. Everything applies
 *  instantly (no save step) and persists locally; nothing here changes the
 *  models or the data, only how the OS looks, moves, and defaults. */
export default function SettingsView() {
  const [settings, update] = useSettings();

  return (
    <div className="max-w-2xl space-y-5">
      <ViewIntro>
        Make the OS yours. Choices apply <strong>instantly</strong> and are remembered on this
        device — they change how the app looks, moves, and defaults, never what the models say.
      </ViewIntro>

      {/* Accent */}
      <Card className="p-5">
        <SectionTitle>Accent colour</SectionTitle>
        <div className="flex gap-4">
          {ACCENTS.map((a) => (
            <button
              key={a.id}
              onClick={() => update({ accent: a.id })}
              aria-pressed={settings.accent === a.id}
              className="group flex flex-col items-center gap-2"
            >
              <span
                className={`h-10 w-10 rounded-full transition ${
                  settings.accent === a.id
                    ? "ring-2 ring-white ring-offset-2 ring-offset-surface"
                    : "group-hover:scale-110"
                }`}
                style={{ background: a.hex }}
              />
              <span className={`text-[12px] ${settings.accent === a.id ? "text-ink" : "text-ink-dim"}`}>
                {a.label}
              </span>
            </button>
          ))}
        </div>
        <p className="mt-3 text-xs text-ink-muted">
          Re-themes highlights, glows, charts' pick colour — everywhere, immediately. Tyre-compound
          colours never change: soft is red, medium is yellow, hard is white, always.
        </p>
      </Card>

      {/* Motion */}
      <Card className="p-5">
        <SectionTitle>Ambient motion</SectionTitle>
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm text-ink-soft">
            The decorative layer — drifting grid, light sweeps, breathing glows. Functional
            feedback (loading states, hover) always stays on.
          </p>
          <button
            role="switch"
            aria-checked={settings.motion}
            onClick={() => update({ motion: !settings.motion })}
            className={`relative h-[26px] w-[46px] shrink-0 rounded-full transition ${
              settings.motion ? "bg-accent" : "bg-surface-inset2 border border-line-ctl"
            }`}
          >
            <span
              className={`absolute top-[3px] h-5 w-5 rounded-full bg-white transition-all ${
                settings.motion ? "left-[23px]" : "left-[3px]"
              }`}
            />
          </button>
        </div>
        <p className="mt-2 text-xs text-ink-muted">
          Also switched off automatically when your system asks for reduced motion.
        </p>
      </Card>

      {/* Density */}
      <Card className="p-5">
        <SectionTitle>Density</SectionTitle>
        <div className="inline-flex rounded-lg border border-line bg-surface-inset p-0.5">
          {(["comfortable", "compact"] as Density[]).map((d) => (
            <button
              key={d}
              onClick={() => update({ density: d })}
              className={`rounded-md px-4 py-1.5 text-sm font-600 capitalize transition ${
                settings.density === d ? "bg-accent text-accent-ink" : "text-ink-muted hover:text-ink"
              }`}
            >
              {d}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-ink-muted">
          Compact tightens paddings and table rows across data-heavy views.
        </p>
      </Card>

      {/* Favourite driver */}
      <FavoriteDriverCard settings={settings} update={update} />

      {/* Time display */}
      <Card className="p-5">
        <SectionTitle>Time display</SectionTitle>
        <div className="inline-flex rounded-lg border border-line bg-surface-inset p-0.5">
          {(["24h", "12h"] as TimeFormat[]).map((f) => (
            <button
              key={f}
              onClick={() => update({ timeFormat: f })}
              className={`rounded-md px-4 py-1.5 text-sm font-600 transition ${
                settings.timeFormat === f ? "bg-accent text-accent-ink" : "text-ink-muted hover:text-ink"
              }`}
            >
              {f === "24h" ? "24-hour" : "12-hour"}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-ink-muted">
          Session times on Home and Calendar — {settings.timeFormat === "24h" ? "17:00" : "5:00 PM"}{" "}
          instead of {settings.timeFormat === "24h" ? "5:00 PM" : "17:00"}. Always your local timezone.
        </p>
      </Card>

      {/* Default season */}
      <DefaultSeasonCard settings={settings} update={update} />

      <Callout>
        Settings live in your browser only — clearing site data resets them to podium gold,
        motion on, comfortable, no favourite driver, 24-hour time, latest season.
      </Callout>

      {/* System */}
      <SystemCard />
    </div>
  );
}

// --- Favourite driver ---------------------------------------------------------
function FavoriteDriverCard({
  settings,
  update,
}: {
  settings: ReturnType<typeof useSettings>[0];
  update: ReturnType<typeof useSettings>[1];
}) {
  const { map } = useDrivers();
  const codes = Object.keys(map).sort((a, b) => (map[a].name ?? a).localeCompare(map[b].name ?? b));

  return (
    <Card className="p-5">
      <div className="mb-1 flex items-baseline justify-between">
        <SectionTitle>Favourite driver</SectionTitle>
        {settings.favoriteDriver && (
          <button
            onClick={() => update({ favoriteDriver: null })}
            className="font-mono text-[11px] text-ink-dim hover:text-ink-soft"
          >
            clear
          </button>
        )}
      </div>
      <p className="mb-3 text-sm text-ink-soft">
        Highlighted everywhere a result table shows drivers — standings, race results, and picked
        by default in Live Race.
      </p>
      {codes.length === 0 ? (
        <p className="text-sm text-ink-muted">Loading drivers…</p>
      ) : (
        <div className="grid grid-cols-4 gap-2 sm:grid-cols-6">
          {codes.map((code) => {
            const isFav = settings.favoriteDriver === code;
            return (
              <button
                key={code}
                onClick={() => update({ favoriteDriver: isFav ? null : code })}
                aria-pressed={isFav}
                title={map[code].name ?? code}
                className={`flex flex-col items-center gap-1.5 rounded-lg border p-2 transition ${
                  isFav
                    ? "border-accent/60 bg-accent/10"
                    : "border-transparent hover:border-line-hover hover:bg-surface-inset/70"
                }`}
              >
                <DriverAvatar code={code} team={map[code].team ?? ""} size={32} />
                <span className={`font-mono text-[10px] ${isFav ? "text-accent" : "text-ink-dim"}`}>
                  {code}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </Card>
  );
}

// --- Default season -----------------------------------------------------------
function DefaultSeasonCard({
  settings,
  update,
}: {
  settings: ReturnType<typeof useSettings>[0];
  update: ReturnType<typeof useSettings>[1];
}) {
  const seasons = useAsync(() => api.allSeasons(), []);
  const list = seasons.data?.seasons ?? [];

  return (
    <Card className="p-5">
      <SectionTitle>Default season</SectionTitle>
      <p className="mb-3 text-sm text-ink-soft">
        Which season Standings, Strategy and Live Race open to. "Latest" always follows the season
        in progress.
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => update({ defaultSeason: null })}
          aria-pressed={settings.defaultSeason == null}
          className={`rounded-md border px-3 py-1.5 font-mono text-[12px] transition ${
            settings.defaultSeason == null
              ? "border-accent/60 bg-accent/10 text-accent"
              : "border-line-ctl text-ink-dim hover:border-line-hover hover:text-ink-soft"
          }`}
        >
          Latest
        </button>
        {list
          .slice()
          .reverse()
          .map((y) => (
            <button
              key={y}
              onClick={() => update({ defaultSeason: y })}
              aria-pressed={settings.defaultSeason === y}
              className={`rounded-md border px-3 py-1.5 font-mono text-[12px] transition ${
                settings.defaultSeason === y
                  ? "border-accent/60 bg-accent/10 text-accent"
                  : "border-line-ctl text-ink-dim hover:border-line-hover hover:text-ink-soft"
              }`}
            >
              {y}
            </button>
          ))}
      </div>
    </Card>
  );
}

// --- System ---------------------------------------------------------------------
function SystemCard() {
  const [health, setHealth] = useState<"checking" | "up" | "down">("checking");

  useEffect(() => {
    let alive = true;
    checkHealth().then((ok) => alive && setHealth(ok ? "up" : "down"));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <Card className="p-5">
      <SectionTitle>System</SectionTitle>
      <div className="space-y-2.5 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-ink-muted">Engine API</span>
          <span className="flex items-center gap-1.5 font-mono text-[12px]">
            <span
              className={`h-[7px] w-[7px] rounded-full ${
                health === "checking"
                  ? "animate-pulse bg-ink-faint"
                  : health === "up"
                    ? "animate-f1pulse bg-accent"
                    : "bg-soft"
              }`}
            />
            <span className={health === "up" ? "text-accent" : health === "down" ? "text-soft" : "text-ink-faint"}>
              {health === "checking" ? "checking…" : health === "up" ? "online" : "unreachable"}
            </span>
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-ink-muted">Version</span>
          <span className="font-mono text-[12px] text-ink-dim">
            v{__APP_VERSION__} · {__BUILD_SHA__}
          </span>
        </div>
      </div>
      <button
        onClick={() => {
          resetSettings();
          window.location.reload();
        }}
        className="mt-4 rounded-md border border-line-ctl px-3 py-1.5 font-mono text-[12px] text-ink-dim transition hover:border-line-hover hover:text-ink-soft"
      >
        Clear saved preferences
      </button>
    </Card>
  );
}
