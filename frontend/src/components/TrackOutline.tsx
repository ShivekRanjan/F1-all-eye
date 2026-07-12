import { useTrackLayouts } from "../lib/useTrackLayouts";

/** Circuit outline SVG (from fastest-lap telemetry) — renders nothing if the
 *  track has no committed layout yet, so callers don't need a fallback. */
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
      />
    </svg>
  );
}
