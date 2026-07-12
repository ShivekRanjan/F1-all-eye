import { useState } from "react";
import { useDrivers } from "../lib/useDrivers";
import { teamColor } from "../lib/format";
import { driverPhotoUrl } from "../lib/driverPhotos";

/** Circular avatar ringed in the driver's team colour: a licensed Wikimedia
 *  photo when we have one (see ATTRIBUTIONS.md), initials otherwise — and
 *  initials again if the photo fails to load. */
export function DriverAvatar({
  code,
  team,
  size = 28,
}: {
  code: string;
  team?: string;
  size?: number;
}) {
  const { meta } = useDrivers();
  const [photoFailed, setPhotoFailed] = useState(false);
  const info = meta(code);
  const resolvedTeam = team ?? info?.team ?? "";
  const color = teamColor(resolvedTeam);
  const initials = info?.name ? initialsOf(info.name) : code.slice(0, 2);
  const photo = !photoFailed ? driverPhotoUrl(code) : null;
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-surface-inset2 font-mono font-700 text-ink"
      style={{
        width: size,
        height: size,
        fontSize: Math.max(9, size * 0.36),
        boxShadow: `0 0 0 1.5px ${color}`,
      }}
    >
      {photo ? (
        <img
          src={photo}
          alt=""
          width={size}
          height={size}
          className="h-full w-full object-cover"
          onError={() => setPhotoFailed(true)}
        />
      ) : (
        initials
      )}
    </span>
  );
}

function initialsOf(fullName: string): string {
  const parts = fullName.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? "";
  const last = parts.at(-1)?.[0] ?? "";
  return (first + last).toUpperCase();
}

/** Driver code with a hover bubble: "ANT ---> Kimi Antonelli". Falls back to
 *  showing just the code if the name lookup hasn't loaded / isn't available. */
export function DriverName({
  code,
  className = "",
}: {
  code: string;
  className?: string;
}) {
  const { meta } = useDrivers();
  const [hover, setHover] = useState(false);
  const name = meta(code)?.name;
  return (
    <span
      className={`relative inline-block ${className}`}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      {code}
      {hover && name && (
        <span
          className="pointer-events-none absolute left-1/2 top-full z-20 mt-1.5 -translate-x-1/2 whitespace-nowrap rounded-md border border-line-card bg-carbon-900 px-2.5 py-1 font-mono text-[11px] text-ink shadow-card animate-fadein"
          role="tooltip"
        >
          {code} <span className="text-accent">{"--->"}</span> {name}
        </span>
      )}
    </span>
  );
}

/** Avatar + hover-named code together, the common standings/podium pairing. */
export function DriverTag({
  code,
  team,
  size = 28,
}: {
  code: string;
  team?: string;
  size?: number;
}) {
  return (
    <span className="inline-flex items-center gap-2">
      <DriverAvatar code={code} team={team} size={size} />
      <DriverName code={code} className="font-700 text-ink" />
    </span>
  );
}
