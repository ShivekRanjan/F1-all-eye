"""Does the next-lap LSTM get better if it also trains on 2025?

The shipped forecaster trains on ``year <= 2024`` and holds out 2025. 2026 was
excluded because it is a regulation reset — which is what makes every 2026 race
a genuinely unseen test, and what earns the headline claim in §8 (+13.4% vs
persistence, winning 11 of 11).

The obvious upgrade is to fold 2025 into training: a whole season of sequences
currently used only for scoring. What is NOT on the table is training on 2026.
That would use the very races the claim is measured on, and would trade a real
result for a number nobody should believe. So:

    A (shipped):  train <= 2024   ->  score 2026
    B (proposed): train <= 2025   ->  score 2026

Same held-out season either way, so the comparison is clean and 2026 stays
untouched. Reports per race, because a mean over 11 races can hide a model that
improves on average while getting worse where it matters.

    python analysis/phase_2026_lstm_retrain.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from f1se.config import PROJECT_ROOT
from f1se.models.lap_time import (
    DEFAULT_WINDOW,
    build_sequence_windows,
    fit_sequence_model,
)

SEED = 0
PROC = PROJECT_ROOT / "data" / "processed"


def _mae(a, b) -> float:
    return float(np.mean(np.abs(np.asarray(a) - np.asarray(b))))


def _fit(laps: pd.DataFrame, label: str):
    w = build_sequence_windows(laps, window=DEFAULT_WINDOW)
    print(f"  {label}: {len(w.y_next):,} windows from {len(laps):,} laps")
    return fit_sequence_model(w, epochs=40, hidden=32, seed=SEED)


def main() -> int:
    dry = pd.read_parquet(PROC / "dry_laps.parquet")
    dry = dry.dropna(subset=["tyre_life", "lap_time_fuel_corr_s"])
    d26 = dry[dry.year >= 2026]
    if d26.empty:
        print("no 2026 laps to score against")
        return 1

    print("Training (CPU, two models)...")
    model_a = _fit(dry[dry.year <= 2024], "A  train <=2024")
    model_b = _fit(dry[dry.year <= 2025], "B  train <=2025")

    rows = []
    for rnd, race in d26.groupby("round"):
        w = build_sequence_windows(race, window=DEFAULT_WINDOW)
        if len(w.y_next) < 30:
            continue
        truth = w.y_next
        pers = _mae(w.y_curr, truth)
        a = _mae(model_a.predict_next(w), truth)
        b = _mae(model_b.predict_next(w), truth)
        rows.append({
            "round": int(rnd), "event": str(race["event_name"].iloc[0])[:22],
            "n": len(truth), "persist": pers, "A_2024": a, "B_2025": b,
            "A_vs_p_%": 100 * (pers - a) / pers,
            "B_vs_p_%": 100 * (pers - b) / pers,
        })

    t = pd.DataFrame(rows)
    print("\n" + t.round(3).to_string(index=False))

    print(f"\nover {len(t)} unseen 2026 races, improvement vs persistence:")
    print(f"  A (train <=2024, shipped) : mean {t['A_vs_p_%'].mean():+.1f}%  "
          f"beats persistence {int((t['A_vs_p_%'] > 0).sum())}/{len(t)}")
    print(f"  B (train <=2025)          : mean {t['B_vs_p_%'].mean():+.1f}%  "
          f"beats persistence {int((t['B_vs_p_%'] > 0).sum())}/{len(t)}")

    diff = t["A_2026" if "A_2026" in t else "A_2024"] - t["B_2025"]
    wins = int((diff > 0).sum())
    print(f"\nB better than A in {wins}/{len(t)} races "
          f"(mean MAE {t['A_2024'].mean():.4f} -> {t['B_2025'].mean():.4f}, "
          f"{100*(t['A_2024'].mean()-t['B_2025'].mean())/t['A_2024'].mean():+.2f}%)")
    print("\nA per-race win count matters more than the mean here: one race with a"
          "\nlot of windows can carry an average without the model being better.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
