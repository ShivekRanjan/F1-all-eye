import type { ReactNode } from "react";
import { compoundColor } from "../lib/format";
import { useLightStep } from "../lib/useLightStep";
import { motionEnabled } from "../lib/motion";

// --- Card -------------------------------------------------------------------
export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl2 border border-line bg-carbon-800 shadow-card transition-[border-color,box-shadow] duration-200 hover:border-line-hover hover:shadow-glow ${className}`}
    >
      {children}
    </div>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="mb-3 text-xs font-700 uppercase tracking-[0.14em] text-ink-muted">
      {children}
    </h2>
  );
}

// --- Metric -----------------------------------------------------------------
export function Metric({
  label,
  value,
  sub,
  accent = false,
  title,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  accent?: boolean;
  title?: string;
}) {
  return (
    <Card className={`p-4 ${accent ? "border-l-2 border-l-accent" : ""}`}>
      <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-ink-faint" title={title}>
        {label}
      </div>
      <div className={`nums mt-1 font-mono text-2xl ${accent ? "text-accent" : "text-ink"}`}>{value}</div>
      {sub != null && <div className="nums mt-1 font-mono text-[11px] text-ink-muted">{sub}</div>}
    </Card>
  );
}

// --- Badge / CompoundPill ---------------------------------------------------
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "red" | "green" | "amber";
}) {
  const tones: Record<string, string> = {
    neutral: "bg-surface-inset2 text-ink-dim",
    red: "bg-soft/15 text-soft",
    green: "bg-emerald-500/15 text-emerald-400",
    amber: "bg-amber-400/15 text-amber-300",
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-600 ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function CompoundPill({ compound }: { compound: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="inline-block h-2.5 w-2.5 rounded-full"
        style={{ background: compoundColor(compound) }}
      />
      {compound}
    </span>
  );
}

// --- EmptyState ---------------------------------------------------------------
/** Full-width empty state — an icon instead of a bare line of text, for the
 *  "no data" cases that aren't errors (no matches, nothing published yet). */
export function EmptyState({
  icon,
  title,
  hint,
}: {
  icon: ReactNode;
  title: string;
  hint?: string;
}) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-line-ctl px-4 py-10 text-center">
      <span className="text-ink-fainter">{icon}</span>
      <div className="text-sm text-ink-muted">{title}</div>
      {hint && <div className="max-w-sm text-xs text-ink-faint">{hint}</div>}
    </div>
  );
}

// --- Callout ----------------------------------------------------------------
export function Callout({
  children,
  tone = "info",
}: {
  children: ReactNode;
  tone?: "info" | "success" | "warn";
}) {
  const tones: Record<string, string> = {
    info: "border-l-sky-500 bg-sky-500/5 text-ink",
    success: "border-l-f1 bg-f1/5 text-ink",
    warn: "border-l-amber-400 bg-amber-400/5 text-amber-100",
  };
  return (
    <div className={`rounded-md border border-line border-l-2 px-3 py-2 text-sm ${tones[tone]}`}>
      {children}
    </div>
  );
}

/** F1 start lights: fill 1→5 red, hold, go dark together ("lights out"),
 *  repeat — the loading state as an actual pre-race ritual instead of a
 *  generic spinner. Degrades to a static gentle pulse when motion is off. */
export function Spinner({ label }: { label?: string }) {
  const step = useLightStep();
  const staticMode = !motionEnabled();
  return (
    <div className="flex items-center gap-2.5 text-sm text-ink-muted">
      <div className={`flex gap-1 ${staticMode ? "animate-pulse" : ""}`}>
        {Array.from({ length: 5 }).map((_, i) => (
          <span
            key={i}
            className="h-2.5 w-2.5 rounded-full transition-colors duration-150"
            style={{
              background: i <= step ? "#ff2b2b" : "#2a1414",
              boxShadow: i <= step ? "0 0 6px rgba(255,43,43,0.55)" : "none",
            }}
          />
        ))}
      </div>
      {label}
    </div>
  );
}

// --- Skeletons ----------------------------------------------------------------
// For the heavy cards (Monte-Carlo, model training): reserve the final height so
// the layout doesn't shift when results land. Spinner stays for quick loads.
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-surface-inset ${className}`} />;
}

export function CardSkeleton({ label, height = 240 }: { label?: string; height?: number }) {
  return (
    <Card className="p-4">
      {label && <Spinner label={label} />}
      <div className="mt-3 space-y-2.5">
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-4 w-2/3" />
        <div style={{ height: Math.max(0, height - 60) }}>
          <Skeleton className="h-full w-full" />
        </div>
      </div>
    </Card>
  );
}

export function ErrorNote({ error }: { error: string }) {
  // A failed fetch (API down / CORS) reads very differently from a real engine
  // error returned with a message — don't mislabel the latter as "unreachable".
  const isNetwork = /failed to fetch|load failed|networkerror|fetch/i.test(error);
  return (
    <Card className="relative overflow-hidden border-l-2 border-l-amber-400 p-4">
      {/* Same status-header language as the rest of the broadcast UI — an
          error is a pit-wall status, not a browser alert. */}
      <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.16em] text-amber-300">
        <span className="h-[7px] w-[7px] animate-f1pulse rounded-full bg-amber-400" />
        {isNetwork ? "Engine offline" : "Engine error"}
      </div>
      {isNetwork ? (
        <>
          <div className="mt-2 text-sm text-ink">
            Couldn’t reach the engine — <span className="text-ink-muted">{error}</span>
          </div>
          <div className="mt-1.5 text-xs text-ink-muted">
            The API may be waking from sleep (free hosting takes ~30–60s) — refresh in a moment.
            Running locally?{" "}
            <code className="rounded bg-surface-inset2 px-1.5 py-0.5 font-mono text-[11px] text-ink">
              uvicorn f1se.api:app
            </code>
          </div>
        </>
      ) : (
        <div className="mt-2 text-sm text-ink">{error}</div>
      )}
    </Card>
  );
}
