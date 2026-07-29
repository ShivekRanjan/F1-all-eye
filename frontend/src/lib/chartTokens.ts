/** Design tokens as literal values, for libraries that can't take CSS classes.
 *
 *  Recharts takes colour *props*, not `className`, so charts genuinely need
 *  hex literals. What they don't need is their own private palette — and that
 *  is what had happened. Three near-duplicates had drifted in, each within a
 *  couple of hex digits of a real token:
 *
 *    #9a9aa6  (18 uses)  vs  ink-dim   #8994a4
 *    #1a212b  ( 6 uses)  vs  line      #1c212b
 *    #ecedf0  ( 5 uses)  vs  ink       #eef1f5
 *
 *  That is the worst kind of drift: every one of them renders as "grey" or
 *  "off-white", so no reviewer catches it by eye and no linter flags it, yet
 *  the chart layer slowly stops matching the app around it.
 *
 *  These MUST stay in sync with `tailwind.config.js`. They are duplicated here
 *  only because Tailwind's config isn't reachable from runtime TS without
 *  pulling the whole config in.
 *
 *  Not included on purpose: the runtime accent (read it from the CSS variable
 *  via `accentHex()` so it follows the user's theme) and team colours (domain
 *  data, already centralised in `lib/format.ts`). */

export const CHART = {
  /** Axis lines, tick labels — the quietest readable step. */
  axis: "#8994a4", // ink-dim
  /** Grid rules. Deliberately below text contrast; it's a background hint. */
  grid: "#1c212b", // line
  /** Primary data line / high-emphasis label. */
  ink: "#eef1f5", // ink
  /** Secondary series. */
  inkSoft: "#dbe0e8", // ink-soft
  /** Tertiary / annotation text. */
  inkMuted: "#aab3c0", // ink-muted
  /** Tooltip and inset panel background. */
  surface: "#11141b", // surface-inset2
} as const;

/** The live accent, resolved from the CSS variable the theme engine sets.
 *
 *  Charts that hardcoded gold broke the moment the runtime accent shipped —
 *  a user on "Night violet" got a violet UI with gold chart lines. Reading the
 *  variable keeps the chart layer honest to the chosen theme. */
export function accentHex(fallback = "#d4af37"): string {
  if (typeof window === "undefined") return fallback;
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue("--accent")
    .trim();
  if (!raw) return fallback;
  const [r, g, b] = raw.split(/[\s,]+/).map(Number);
  if ([r, g, b].some((n) => !Number.isFinite(n))) return fallback;
  return "#" + [r, g, b].map((n) => n.toString(16).padStart(2, "0")).join("");
}
