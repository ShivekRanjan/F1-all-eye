import { useEffect, useState } from "react";
import { api } from "../api/client";

export interface DriverMeta {
  name: string | null;
  team: string | null;
  country: string | null;
}

// Process-wide cache + in-flight promise: the driver lookup is small and
// shared by Home, Standings and Race Hub — fetch it once for the whole app.
let cache: Record<string, DriverMeta> | null = null;
let inflight: Promise<Record<string, DriverMeta>> | null = null;

function load(): Promise<Record<string, DriverMeta>> {
  if (cache) return Promise.resolve(cache);
  if (!inflight) {
    inflight = api
      .driversMeta()
      .then((r) => (cache = r.drivers))
      .catch(() => ({}) as Record<string, DriverMeta>);
  }
  return inflight;
}

/** The code→meta map (empty until loaded). `fullName(code)` falls back to the
 *  code itself, so the UI is never blank while it loads or if it 404s. */
export function useDrivers() {
  const [map, setMap] = useState<Record<string, DriverMeta>>(cache ?? {});
  useEffect(() => {
    let alive = true;
    load().then((m) => alive && setMap(m));
    return () => {
      alive = false;
    };
  }, []);
  const meta = (code: string): DriverMeta | undefined => map[code];
  const fullName = (code: string): string => map[code]?.name ?? code;
  return { map, meta, fullName };
}
