"""Is the published shrinkage gain measured in-sample?

`phase_2026_validation.py` reports the shrunk model at 0.4412 MAE on 2026 laps
against the pre-2026 prior's 0.5066 — a large win. But it fits the shrunk model
on `dry` (which *includes* the 2026 laps) and then scores it on those same 2026
laps. The prior, fitted only on `year < 2026`, is genuinely out-of-sample. So the
headline compares an in-sample model against an out-of-sample one.

This isolates that. For every 2026 race, score four things on the held-out race:

* naive — no degradation at all
* prior — fitted on pre-2026 only (always out-of-sample)
* shrunk, in-sample — fitted on everything, including this race
* shrunk, leave-one-race-out — fitted on everything except this race

The gap between the last two is the leakage. Whatever survives it is the real
benefit of shrinkage.

    python analysis/phase_2026_shrinkage_honest.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from f1se.config import PROJECT_ROOT
from f1se.models.degradation import (
    fit_linear_baseline,
    linear_shape,
    naive_pace_loss_mae,
    shape_mae,
)
from f1se.models.era import fit_era_shrunk_degradation

K = 150.0


def main() -> int:
    dry = pd.read_parquet(PROJECT_ROOT / "data" / "processed" / "dry_laps.parquet")
    dry = dry.dropna(subset=["tyre_life", "lap_time_fuel_corr_s"])
    d26 = dry[dry.year >= 2026]
    races = sorted(d26["round"].unique())

    prior = fit_linear_baseline(dry[dry.year < 2026])
    insample = fit_era_shrunk_degradation(dry, target_min_year=2026, shrinkage_laps=K)

    rows = []
    for r in races:
        held = d26[d26["round"] == r]
        if len(held) < 50:
            continue
        loro_fit = fit_era_shrunk_degradation(
            dry[~((dry.year >= 2026) & (dry["round"] == r))],
            target_min_year=2026, shrinkage_laps=K)
        rows.append({
            "round": int(r),
            "naive": naive_pace_loss_mae(held),
            "prior": shape_mae(linear_shape(prior, held), held),
            "shrunk_insample": shape_mae(linear_shape(insample, held), held),
            "shrunk_loro": shape_mae(linear_shape(loro_fit, held), held),
        })

    t = pd.DataFrame(rows)
    print(t.round(4).to_string(index=False))

    m = t.mean(numeric_only=True)
    naive = m["naive"]
    print(f"\nmean over {len(t)} races (pace-loss MAE, lower = better):")
    for label, key, note in [
        ("naive (no degradation)", "naive", ""),
        ("pre-2026 prior", "prior", "out-of-sample"),
        ("shrunk, in-sample", "shrunk_insample", "<- what the docs report"),
        ("shrunk, leave-one-race-out", "shrunk_loro", "<- the honest number"),
    ]:
        print(f"  {label:<28} {m[key]:.4f}  ({100*(naive-m[key])/naive:+5.1f}% vs naive)  {note}")

    leak = 100 * (m["shrunk_loro"] - m["shrunk_insample"]) / m["shrunk_insample"]
    real = 100 * (m["prior"] - m["shrunk_loro"]) / m["prior"]
    print(f"\nleakage inflation: in-sample is {leak:.1f}% optimistic vs LORO")
    print(f"real shrinkage benefit over the prior, out-of-sample: {real:+.1f}%")
    wins = int((t["shrunk_loro"] < t["prior"]).sum())
    print(f"races where LORO shrinkage beats the prior: {wins}/{len(t)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
