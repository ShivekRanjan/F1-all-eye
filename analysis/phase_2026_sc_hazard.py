"""Is the safety-car hazard really 'transferable' across the 2026 reset?

METHODOLOGY 7 splits the engine's components in two. Regime-sensitive ones
(base pace, degradation) get the shrinkage treatment. Transferable ones —
pit-lane loss, SC hazard, fuel physics — are pooled across all seasons on the
argument that a safety car is a property of circuits and marshalling, not of
the cars.

That was an assumption, never a measurement. New cars can plausibly change it:
different failure modes, different closing speeds, different crash frequency.
And it is not a harmless assumption — SC probability drives when the simulator
thinks a cheap stop is coming, so it moves the strategy call directly.

With 11 races of 2026 track status there is finally enough to check. Compares
the 2026 per-lap SC hazard against the pre-2026 pooled rate, with a bootstrap
interval so 'different' means more than small-sample noise.

    python analysis/phase_2026_sc_hazard.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from f1se.config import PROJECT_ROOT
from f1se.sim.safety_car import sc_laps_in_race, sc_period_durations

RNG = np.random.default_rng(0)
N_BOOT = 10000


def race_stats(status: pd.DataFrame) -> pd.DataFrame:
    """Per race: laps run, number of distinct SC periods, and their lengths."""
    rows = []
    for (year, rnd), g in status.groupby(["year", "round"]):
        laps = int(g["lap_number"].max()) if len(g) else 0
        if laps <= 0:
            continue
        sc = sc_laps_in_race(g)
        durations = sc_period_durations(sc)
        rows.append({"year": int(year), "round": int(rnd),
                     "event": str(g["event_name"].iloc[0]),
                     "laps": laps, "periods": len(durations),
                     "sc_laps": len(sc),
                     "mean_dur": float(np.mean(durations)) if durations else 0.0})
    return pd.DataFrame(rows)


def _boot_rate(periods: np.ndarray, laps: np.ndarray) -> np.ndarray:
    """Bootstrap the pooled per-lap hazard by resampling whole races."""
    n = len(periods)
    idx = RNG.integers(0, n, size=(N_BOOT, n))
    return periods[idx].sum(axis=1) / laps[idx].sum(axis=1)


def main() -> int:
    fp = PROJECT_ROOT / "data" / "processed" / "track_status.parquet"
    if not fp.exists():
        print("no track_status.parquet — run: python -m f1se.data.ingest status <years>")
        return 1
    status = pd.read_parquet(fp)
    stats = race_stats(status)
    pre, cur = stats[stats.year < 2026], stats[stats.year >= 2026]
    if cur.empty:
        print("no 2026 track status ingested yet")
        return 1

    print(f"pre-2026: {len(pre)} races   2026: {len(cur)} races\n")
    print(cur[["round", "event", "laps", "periods", "sc_laps"]].to_string(index=False))

    out = {}
    for label, d in (("pre-2026", pre), ("2026", cur)):
        rate = d["periods"].sum() / d["laps"].sum()
        boot = _boot_rate(d["periods"].to_numpy(), d["laps"].to_numpy())
        lo, hi = np.percentile(boot, [2.5, 97.5])
        out[label] = (rate, lo, hi, d["periods"].sum(), d["laps"].sum())
        print(f"\n{label}: {d['periods'].sum()} SC periods over {d['laps'].sum()} laps")
        print(f"  per-lap hazard {rate:.5f}   95% CI [{lo:.5f}, {hi:.5f}]")
        print(f"  = {rate * d['laps'].mean():.2f} SC periods per race")

    r_pre, lo_pre, hi_pre, _, _ = out["pre-2026"]
    r_cur, lo_cur, hi_cur, _, _ = out["2026"]
    print(f"\nmodel default (SafetyCarModel.prob_per_lap): 0.013")
    print(f"2026 vs pre-2026: {100 * (r_cur - r_pre) / r_pre:+.1f}%")
    overlap = not (hi_cur < lo_pre or hi_pre < lo_cur)
    print("\nverdict:", "CONSISTENT — 2026's interval overlaps the pre-2026 rate, so"
          "\n  pooling across the reset is supported by the data, not just assumed."
          if overlap else
          "DIFFERENT — the intervals are disjoint; 2026's SC rate is not the"
          "\n  pre-2026 rate, and pooling biases every strategy call that prices a stop.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
