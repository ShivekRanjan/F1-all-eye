import { useCountUp } from "../lib/useCountUp";

/** A number that ticks toward its new value instead of snapping — for the
 *  stats that change on refresh (points, title odds). `format` receives the
 *  in-flight interpolated value, so a percentage formatter ticks smoothly
 *  through the animation, not just at the endpoints. */
export function AnimatedNumber({
  value,
  format = (n: number) => n.toFixed(0),
  className = "",
}: {
  value: number;
  format?: (n: number) => string;
  className?: string;
}) {
  const display = useCountUp(value);
  return <span className={className}>{format(display)}</span>;
}
