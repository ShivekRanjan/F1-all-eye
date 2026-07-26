"""Is the shrinkage constant k=150 right, now that it can be tested?

`fit_era_shrunk_degradation` blends each per-group 2026 slope toward the
pre-2026 prior as `(n*est + k*prior)/(n + k)`, with `k = shrinkage_laps = 150`.
That k is a prior-strength *guess*, made when 2026 had two races and there was
no honest way to tune it — a small k would have trusted a handful of noisy laps,
a large k would have ignored the reset entirely.

With 11 races there is enough data to stop guessing. Leave-one-race-out over the
2026 races: fit the shrunk model with every race but one, score pace-loss MAE on
the held-out race, average. No race is ever fit and scored at once, so the sweep
can't reward memorising a race.

    python analysis/phase_2026_shrinkage_sweep.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from f1se.config import PROJECT_ROOT
from f1se.models.degradation import linear_shape, naive_pace_loss_mae, shape_mae
from f1se.models.era import fit_era_shrunk_degradation

GRID = [0.0, 25.0, 50.0, 100.0, 150.0, 250.0, 400.0, 800.0, 2000.0]
CURRENT = 150.0


def main() -> int:
    dry = pd.read_parquet(PROJECT_ROOT / "data" / "processed" / "dry_laps.parquet")
    dry = dry.dropna(subset=["tyre_life", "lap_time_fuel_corr_s"])
    d26 = dry[dry.year >= 2026]
    races = sorted(d26["round"].unique())
    print(f"2026: {len(d26):,} dry laps over {len(races)} races "
          f"(pre-2026 prior: {len(dry) - len(d26):,} laps)\n")

    rows = []
    for k in GRID:
        fold_mae, fold_naive = [], []
        for r in races:
            held = d26[d26["round"] == r]
            if len(held) < 50:
                continue
            # Everything except the held-out race — pre-2026 prior included.
            train = dry[~((dry.year >= 2026) & (dry["round"] == r))]
            model = fit_era_shrunk_degradation(train, target_min_year=2026,
                                               shrinkage_laps=k)
            fold_mae.append(shape_mae(linear_shape(model, held), held))
            fold_naive.append(naive_pace_loss_mae(held))
        rows.append({"k": k, "mae": float(np.mean(fold_mae)),
                     "vs_naive_pct": 100 * (np.mean(fold_naive) - np.mean(fold_mae))
                     / np.mean(fold_naive)})

    tbl = pd.DataFrame(rows).sort_values("k")
    best = tbl.loc[tbl["mae"].idxmin()]
    cur = tbl.loc[tbl["k"] == CURRENT].iloc[0]

    print("leave-one-race-out pace-loss MAE by shrinkage k (lower = better):")
    for t in tbl.itertuples(index=False):
        mark = "  <- current" if t.k == CURRENT else ""
        star = " *BEST*" if t.k == best["k"] else ""
        print(f"  k={t.k:>7.0f}   MAE {t.mae:.4f}   ({t.vs_naive_pct:+.1f}% vs naive){mark}{star}")

    gain = (cur["mae"] - best["mae"]) / cur["mae"] * 100
    print(f"\ncurrent k={CURRENT:.0f}: MAE {cur['mae']:.4f}")
    print(f"best    k={best['k']:.0f}: MAE {best['mae']:.4f}   ({gain:+.2f}% vs current)")
    print("\nk=0 is 'trust 2026 only'; k=2000 is 'ignore 2026'. If the curve is flat"
          "\nbetween them the exact value doesn't matter much — which is itself the"
          "\nresult worth reporting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
