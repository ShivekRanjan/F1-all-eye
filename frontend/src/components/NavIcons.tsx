// Sidebar nav icons — deliberately simple geometric line art (circles, rects,
// straight paths only) so they read cleanly at 16px and match the app's
// restrained stroke-icon language (TrackOutline, the podium marks) rather
// than detailed pictograms that turn to mud at this size.
import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

const base = {
  width: 16,
  height: 16,
  viewBox: "0 0 16 16",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.5,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function HomeIcon(p: IconProps) {
  return (
    <svg {...base} {...p}>
      <path d="M2.5 7.5 8 2.5l5.5 5" />
      <path d="M4 6.5V13.5h8V6.5" />
    </svg>
  );
}

export function TargetIcon(p: IconProps) {
  return (
    <svg {...base} {...p}>
      <circle cx="8" cy="8" r="5.5" />
      <circle cx="8" cy="8" r="2.5" />
      <circle cx="8" cy="8" r="0.6" fill="currentColor" />
    </svg>
  );
}

export function SwapIcon(p: IconProps) {
  return (
    <svg {...base} {...p}>
      <path d="M3 5.5h9M9 3l3 2.5-3 2.5" />
      <path d="M13 10.5H4M7 8l-3 2.5 3 2.5" />
    </svg>
  );
}

export function CalendarIcon(p: IconProps) {
  return (
    <svg {...base} {...p}>
      <rect x="2.5" y="3.5" width="11" height="10" rx="1" />
      <path d="M2.5 6.5h11M5.5 2v3M10.5 2v3" />
    </svg>
  );
}

export function WheelIcon(p: IconProps) {
  return (
    <svg {...base} {...p}>
      <circle cx="8" cy="8" r="5.5" />
      <circle cx="8" cy="8" r="1.6" />
      <path d="M8 2.5v4M8 9.5v4M3.6 5.4l3 2.3M9.4 8.3l3 2.3M12.4 5.4l-3 2.3M6.6 8.3l-3 2.3" />
    </svg>
  );
}

export function LiveIcon(p: IconProps) {
  return (
    <svg {...base} {...p}>
      <circle cx="8" cy="8" r="1.4" fill="currentColor" />
      <path d="M5.3 5.3a4 4 0 0 0 0 5.4M10.7 5.3a4 4 0 0 1 0 5.4" />
      <path d="M3.1 3.1a7.5 7.5 0 0 0 0 9.8M12.9 3.1a7.5 7.5 0 0 1 0 9.8" />
    </svg>
  );
}

export function BarsIcon(p: IconProps) {
  return (
    <svg {...base} {...p}>
      <path d="M3.5 13.5v-4M8 13.5v-8M12.5 13.5v-6" />
    </svg>
  );
}

export function HelmetIcon(p: IconProps) {
  return (
    <svg {...base} {...p}>
      <path d="M3 12.5v-3a5 5 0 0 1 10 0v3" />
      <path d="M3 12.5h10v.5a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z" />
      <path d="M9.5 7.5h3.5" />
    </svg>
  );
}

export function DiceIcon(p: IconProps) {
  return (
    <svg {...base} {...p}>
      <rect x="2.5" y="2.5" width="11" height="11" rx="2" />
      <circle cx="5.5" cy="5.5" r="0.6" fill="currentColor" />
      <circle cx="10.5" cy="5.5" r="0.6" fill="currentColor" />
      <circle cx="8" cy="8" r="0.6" fill="currentColor" />
      <circle cx="5.5" cy="10.5" r="0.6" fill="currentColor" />
      <circle cx="10.5" cy="10.5" r="0.6" fill="currentColor" />
    </svg>
  );
}

export function NewsIcon(p: IconProps) {
  return (
    <svg {...base} {...p}>
      <rect x="2.5" y="3.5" width="9" height="9" rx="1" />
      <path d="M11.5 6.5h2v5.5a1.5 1.5 0 0 1-1.5 1.5h-8" />
      <path d="M4.5 6h5M4.5 8.5h5M4.5 11h3" />
    </svg>
  );
}

export function InfoIcon(p: IconProps) {
  return (
    <svg {...base} {...p}>
      <circle cx="8" cy="8" r="5.5" />
      <path d="M8 7.3v4" />
      <circle cx="8" cy="5" r="0.6" fill="currentColor" />
    </svg>
  );
}

export function SlidersIcon(p: IconProps) {
  return (
    <svg {...base} {...p}>
      <path d="M3 4.5h10M3 8h10M3 11.5h10" />
      <circle cx="6" cy="4.5" r="1.4" fill="currentColor" stroke="none" />
      <circle cx="10.5" cy="8" r="1.4" fill="currentColor" stroke="none" />
      <circle cx="7.5" cy="11.5" r="1.4" fill="currentColor" stroke="none" />
    </svg>
  );
}

// --- Empty-state icons (larger default size, same restrained line style) ---
const emptyBase = { ...base, width: 28, height: 28 };

export function SearchOffIcon(p: IconProps) {
  return (
    <svg {...emptyBase} {...p}>
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.3 10.3 14 14" />
    </svg>
  );
}

export function NoSignalIcon(p: IconProps) {
  return (
    <svg {...emptyBase} {...p}>
      <rect x="2.5" y="3.5" width="9" height="9" rx="1" />
      <path d="M11.5 6.5h2v5.5a1.5 1.5 0 0 1-1.5 1.5h-8" />
      <path d="M2 2l12 12" />
    </svg>
  );
}
