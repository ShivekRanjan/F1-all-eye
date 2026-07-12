import { useEffect, useState } from "react";
import { api } from "../api/client";

export interface TrackLayout {
  path: string;
  viewbox: number;
}

// Process-wide cache + in-flight promise — one small fetch shared by the
// Strategy circuit picker and the Race Hub header.
let cache: Record<string, TrackLayout> | null = null;
let inflight: Promise<Record<string, TrackLayout>> | null = null;

function load(): Promise<Record<string, TrackLayout>> {
  if (cache) return Promise.resolve(cache);
  if (!inflight) {
    inflight = api
      .trackLayouts()
      .then((r) => (cache = r.tracks))
      .catch(() => ({}) as Record<string, TrackLayout>);
  }
  return inflight;
}

/** The track→outline map (empty until loaded / if a circuit has none yet). */
export function useTrackLayouts() {
  const [map, setMap] = useState<Record<string, TrackLayout>>(cache ?? {});
  useEffect(() => {
    let alive = true;
    load().then((m) => alive && setMap(m));
    return () => {
      alive = false;
    };
  }, []);
  return map;
}
