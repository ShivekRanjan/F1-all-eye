import { useTrackLayouts } from "../lib/useTrackLayouts";

/** Large, very faint circuit outline for a card's background — the "you are
 *  at this track" ambient cue. Position/size via className (caller picks a
 *  corner); renders nothing if the track has no committed layout. Put it
 *  first in a `relative overflow-hidden` container so content stacks above. */
export function TrackWatermark({ track, className = "" }: { track: string; className?: string }) {
  const layouts = useTrackLayouts();
  const layout = layouts[track];
  if (!layout) return null;
  return (
    <svg
      key={track}
      viewBox={`0 0 ${layout.viewbox} ${layout.viewbox}`}
      className={`pointer-events-none absolute text-accent opacity-[0.05] ${className}`}
      aria-hidden="true"
    >
      <path
        d={layout.path}
        fill="none"
        stroke="currentColor"
        strokeWidth={5}
        strokeLinecap="round"
        strokeLinejoin="round"
        pathLength={100}
        strokeDasharray={100}
        className="animate-trackdraw"
      />
    </svg>
  );
}

/** Circuit outline SVG (from fastest-lap telemetry) — renders nothing if the
 *  track has no committed layout yet, so callers don't need a fallback.
 *  Draws itself in on mount (and re-draws if `track` changes, via the key)
 *  instead of appearing stamped. */
export function TrackOutline({
  track,
  size = 40,
  className = "",
}: {
  track: string;
  size?: number;
  className?: string;
}) {
  const layouts = useTrackLayouts();
  const layout = layouts[track];
  if (!layout) return null;
  return (
    <svg
      key={track}
      viewBox={`0 0 ${layout.viewbox} ${layout.viewbox}`}
      width={size}
      height={size}
      className={`shrink-0 ${className}`}
    >
      <path
        d={layout.path}
        fill="none"
        stroke="currentColor"
        strokeWidth={7}
        strokeLinecap="round"
        strokeLinejoin="round"
        pathLength={100}
        strokeDasharray={100}
        className="animate-trackdraw"
      />
    </svg>
  );
}
