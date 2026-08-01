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


VSC_CODES = ("6", "7")  # 6 = VSC deployed, 7 = VSC ending


def _laps_with(g: pd.DataFrame, codes) -> list[int]:
    """Laps where most cars show any of ``codes`` — same rule as sc_laps_in_race."""
    by_lap = g.groupby("lap_number")["track_status"].apply(
        lambda s: s.astype("string").str.contains("|".join(codes), na=False).mean()
    )
    return sorted(int(lap) for lap, frac in by_lap.items() if frac > 0.5)


def race_stats(status: pd.DataFrame) -> pd.DataFrame:
    """Per race: laps run, distinct SC periods, and the same counting VSC too.

    The engine's ``sc_laps_in_race`` matches only track-status ``4`` (full safety
    car). A **virtual** safety car (``6``/``7``) also slows the field and also
    makes a stop cheaper — less so than a full SC, since the field never bunches
    — and it is about as frequent. Counting only ``4`` therefore understates how
    often a cheap-stop window appears. Both are reported here.
    """
    rows = []
    for (year, rnd), g in status.groupby(["year", "round"]):
        laps = int(g["lap_number"].max()) if len(g) else 0
        if laps <= 0:
            continue
        sc = sc_laps_in_race(g)
        sc_set = set(sc)
        vsc_only = [lap for lap in _laps_with(g, VSC_CODES) if lap not in sc_set]
        both = sorted(set(sc) | set(vsc_only))
        rows.append({"year": int(year), "round": int(rnd),
                     "event": str(g["event_name"].iloc[0]),
                     "laps": laps,
                     "periods": len(sc_period_durations(sc)),
                     "sc_laps": len(sc),
                     "vsc_laps": len(vsc_only),
                     "periods_incl_vsc": len(sc_period_durations(both)),
                     "mean_dur": float(np.mean(sc_period_durations(sc)))
                     if sc_period_durations(sc) else 0.0})
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
    print(cur[["round", "event", "laps", "periods", "sc_laps", "vsc_laps",
               "periods_incl_vsc"]].to_string(index=False))

    out = {}
    for label, d in (("pre-2026", pre), ("2026", cur)):
        rate = d["periods"].sum() / d["laps"].sum()
        boot = _boot_rate(d["periods"].to_numpy(), d["laps"].to_numpy())
        lo, hi = np.percentile(boot, [2.5, 97.5])
        out[label] = (rate, lo, hi, d["periods"].sum(), d["laps"].sum())
        print(f"\n{label}: {d['periods'].sum()} SC periods over {d['laps'].sum()} laps")
        print(f"  per-lap hazard {rate:.5f}   95% CI [{lo:.5f}, {hi:.5f}]")
        print(f"  = {rate * d['laps'].mean():.2f} SC periods per race")
        r2 = d["periods_incl_vsc"].sum() / d["laps"].sum()
        print(f"  incl. VSC: {d['periods_incl_vsc'].sum()} periods -> hazard {r2:.5f} "
              f"({100 * (r2 - rate) / rate:+.0f}% vs SC-only)")

    r_pre, lo_pre, hi_pre, _, _ = out["pre-2026"]
    r_cur, lo_cur, hi_cur, _, _ = out["2026"]
    print("\nmodel default (SafetyCarModel.prob_per_lap): 0.013")

    def verdict(label, rp, lp, hp, rc, lc, hc):
        print(f"\n[{label}] 2026 vs pre-2026: {100 * (rc - rp) / rp:+.1f}%")
        print(f"  pre-2026 {rp:.5f} [{lp:.5f}, {hp:.5f}]   2026 {rc:.5f} [{lc:.5f}, {hc:.5f}]")
        if not (hc < lp or hp < lc):
            print("  CONSISTENT — intervals overlap; pooling across the reset is supported.")
        else:
            print("  DIFFERENT — intervals are disjoint. Pooling biases every strategy")
            print("  call that prices a stop against a neutralisation.")

    verdict("safety car only — what the engine models",
            r_pre, lo_pre, hi_pre, r_cur, lo_cur, hi_cur)

    # Same test, counting VSC as a neutralisation too. The engine does not: it
    # matches track status "4" alone, so a VSC-only race looks event-free.
    bp = _boot_rate(pre["periods_incl_vsc"].to_numpy(), pre["laps"].to_numpy())
    bc = _boot_rate(cur["periods_incl_vsc"].to_numpy(), cur["laps"].to_numpy())
    rp2 = pre["periods_incl_vsc"].sum() / pre["laps"].sum()
    rc2 = cur["periods_incl_vsc"].sum() / cur["laps"].sum()
    verdict("safety car + VSC — what actually neutralises a race",
            rp2, *np.percentile(bp, [2.5, 97.5]), rc2, *np.percentile(bc, [2.5, 97.5]))

    sc_only = int(cur["periods"].sum())
    all_n = int(cur["periods_incl_vsc"].sum())
    blind = int((cur["periods"].eq(0) & cur["periods_incl_vsc"].gt(0)).sum())
    print(f"\ncoverage: the engine counts {sc_only} of {all_n} 2026 neutralisations "
          f"({100 * sc_only / all_n:.0f}%).")
    print(f"  {blind} of {len(cur)} races had no full SC but did have a VSC — the engine")
    print("  sees those as entirely event-free.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
