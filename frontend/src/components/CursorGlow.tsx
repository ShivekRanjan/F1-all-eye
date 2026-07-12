import { useEffect, useRef } from "react";
import { motionEnabled } from "../lib/motion";

/** A soft accent-coloured spotlight that follows the cursor, layered behind
 *  every screen (App.tsx renders it once, fixed, above the grid-drift layer).
 *  rAF-throttled so it costs nothing beyond a single style write per frame;
 *  off entirely when motion is disabled. */
export function CursorGlow() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let raf = 0;
    let x = window.innerWidth / 2;
    let y = window.innerHeight / 3;

    const paint = () => {
      el.style.background = `radial-gradient(560px circle at ${x}px ${y}px, rgb(var(--accent) / 0.05), transparent 60%)`;
      raf = 0;
    };
    const onMove = (e: MouseEvent) => {
      if (!motionEnabled()) return;
      x = e.clientX;
      y = e.clientY;
      if (!raf) raf = requestAnimationFrame(paint);
    };

    // Listener always attached; the motion check happens per-move so toggling
    // Settings' motion switch at runtime takes effect immediately either way.
    window.addEventListener("mousemove", onMove, { passive: true });
    return () => {
      window.removeEventListener("mousemove", onMove);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  return <div ref={ref} className="pointer-events-none fixed inset-0 z-0" />;
}
