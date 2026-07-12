import { useEffect, useRef } from "react";
import { motionEnabled } from "./motion";

/** Cursor-reactive parallax: attach `containerRef` to the area that should
 *  track the mouse, `targetRef` to the element that should drift within it.
 *  Direct DOM writes (no React state) so it costs nothing per frame beyond
 *  a single transform update; off when motion is disabled. */
export function useParallax<C extends HTMLElement, T extends HTMLElement>(maxPx = 8) {
  const containerRef = useRef<C>(null);
  const targetRef = useRef<T>(null);

  useEffect(() => {
    const container = containerRef.current;
    const target = targetRef.current;
    if (!container || !target) return;

    const onMove = (e: MouseEvent) => {
      if (!motionEnabled()) return;
      const rect = container.getBoundingClientRect();
      const nx = (e.clientX - rect.left) / rect.width - 0.5; // -0.5..0.5
      const ny = (e.clientY - rect.top) / rect.height - 0.5;
      target.style.transform = `translate(${(nx * maxPx * 2).toFixed(1)}px, ${(ny * maxPx * 2).toFixed(1)}px)`;
    };
    const onLeave = () => {
      target.style.transform = "translate(0px, 0px)";
    };

    container.addEventListener("mousemove", onMove);
    container.addEventListener("mouseleave", onLeave);
    return () => {
      container.removeEventListener("mousemove", onMove);
      container.removeEventListener("mouseleave", onLeave);
    };
  }, [maxPx]);

  return { containerRef, targetRef };
}
