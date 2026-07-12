import { useEffect, useState } from "react";
import { motionEnabled } from "./motion";

/** Drives an F1 start-light sequence: lights fill 0..count-1 one at a time,
 *  hold lit, then go dark together ("lights out") and repeat. Returns the
 *  index of the last lit light, or -1 when all are dark. Falls back to a
 *  static "all lit" state when motion is disabled (paired with a gentle
 *  CSS pulse by the caller, not this hook's sequential chase). */
export function useLightStep(count = 5, onMs = 220, holdMs = 450, offMs = 500): number {
  const [step, setStep] = useState(-1);

  useEffect(() => {
    if (!motionEnabled()) {
      setStep(count - 1);
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const cycle = (i: number) => {
      if (cancelled) return;
      if (i < count) {
        setStep(i);
        timer = setTimeout(() => cycle(i + 1), onMs);
      } else {
        timer = setTimeout(() => {
          setStep(-1);
          timer = setTimeout(() => cycle(0), offMs);
        }, holdMs);
      }
    };
    cycle(0);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [count, onMs, holdMs, offMs]);

  return step;
}
