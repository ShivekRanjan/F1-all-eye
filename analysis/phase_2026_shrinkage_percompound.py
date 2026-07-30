"""Should each compound get its own shrinkage constant?

§13 swept a single global `k` and found the curve flat. It left one question
open: lap counts differ sharply by compound — the hards carry several times the
evidence of the softs — so in principle each deserves its own prior weight. A
compound with plenty of 2026 laps should lean on the prior less.

Tested the same way as the global sweep, and for the same reason: leave-one-
race-out, so no fit is ever scored on a race it saw. Per-compound tuning has far
more freedom than one global knob (three parameters instead of one), which is
exactly the setting where an in-sample search invents an improvement.

    python analysis/phase_2026_shrinkage_percompound.py
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from f1se.config import PROJECT_ROOT
from f1se.models.degradation import linear_shape, naive_pace_loss_mae, shape_mae
from f1se.models.era import fit_era_shrunk_degradation

GRID = [25.0, 150.0, 800.0]          # trust-2026 / current / trust-prior
COMPOUNDS = ["SOFT", "MEDIUM", "HARD"]
CURRENT = 150.0


def loro_mae(dry: pd.DataFrame, d26: pd.DataFrame, races, k) -> float:
    """Mean leave-one-race-out pace-loss MAE for a shrinkage setting."""
    errs = []
    for r in races:
        held = d26[d26["round"] == r]
        if len(held) < 50:
            continue
        train = dry[~((dry.year >= 2026) & (dry["round"] == r))]
        model = fit_era_shrunk_degradation(train, target_min_year=2026, shrinkage_laps=k)
        errs.append(shape_mae(linear_shape(model, held), held))
    return float(np.mean(errs))


def main() -> int:
    dry = pd.read_parquet(PROJECT_ROOT / "data" / "processed" / "dry_laps.parquet")
    dry = dry.dropna(subset=["tyre_life", "lap_time_fuel_corr_s"])
    d26 = dry[dry.year >= 2026]
    races = sorted(d26["round"].unique())

    counts = d26.groupby("compound").size().to_dict()
    print("2026 laps per compound:", {c: int(counts.get(c, 0)) for c in COMPOUNDS})
    naive = float(np.mean([naive_pace_loss_mae(d26[d26["round"] == r])
                           for r in races if len(d26[d26["round"] == r]) >= 50]))

    base = loro_mae(dry, d26, races, CURRENT)
    print(f"\nglobal k={CURRENT:.0f}: LORO MAE {base:.4f}  ({100*(naive-base)/naive:+.1f}% vs naive)\n")

    print(f"per-compound grid ({len(GRID)**3} combinations, leave-one-race-out):")
    rows = []
    for combo in itertools.product(GRID, repeat=3):
        k = dict(zip(COMPOUNDS, combo))
        mae = loro_mae(dry, d26, races, k)
        rows.append({**{f"k_{c}": v for c, v in k.items()}, "mae": mae})

    t = pd.DataFrame(rows).sort_values("mae")
    print(t.head(5).to_string(index=False))
    print("  ...")
    print(t.tail(2).to_string(index=False))

    best = t.iloc[0]
    gain = (base - best["mae"]) / base * 100
    print(f"\nbest per-compound: {best['mae']:.4f}   vs global {base:.4f}   ({gain:+.2f}%)")
    print(f"spread across all {len(t)} combinations: "
          f"{t['mae'].min():.4f} .. {t['mae'].max():.4f} "
          f"({100*(t['mae'].max()-t['mae'].min())/t['mae'].min():.2f}%)")
    print("\nRead: a gain worth having should be large relative to that spread AND")
    print("to the race-to-race variation. Three free parameters can always find")
    print("something; the question is whether it is signal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
