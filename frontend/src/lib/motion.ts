/** Whether JS-driven ambient motion (cursor glow, parallax) should run —
 *  mirrors the CSS motion gate (index.css) for effects CSS alone can't
 *  express. Checked at effect-setup time and on every settings change. */
export function motionEnabled(): boolean {
  if (typeof document === "undefined") return true;
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return false;
  return document.documentElement.getAttribute("data-motion") !== "off";
}
