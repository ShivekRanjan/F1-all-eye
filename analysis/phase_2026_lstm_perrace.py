"""The LSTM's 2026 result, per race, instead of one lucky number.

The advertised "+18% vs persistence on a fully unseen race" is a single race
(Austria). One race is a data point, not a result — it could as easily have been
a bad one. The model trains on ``year <= 2024`` and never sees 2026 at all, so
every 2026 race is a genuine unseen test and there are now eleven of them.

Reports the win over persistence race by race, with mean, spread, median and
win-rate. Also carries the rolling-slope baseline, since beating "repeat the
last lap" is a low bar and the trend extrapolation is the harder one.

    python analysis/phase_2026_lstm_perrace.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from f1se.config import PROJECT_ROOT
from f1se.models.lap_time import NumpyLapForecaster, build_sequence_windows

PROC = PROJECT_ROOT / "data" / "processed"


def main() -> int:
    model = NumpyLapForecaster.load(PROC / "lstm_nextlap.npz")
    dry = pd.read_parquet(PROC / "dry_laps.parquet")
    d26 = dry[dry.year >= 2026]
    if d26.empty:
        print("no 2026 laps")
        return 1

    rows = []
    for rnd, race in d26.groupby("round"):
        w = build_sequence_windows(race, window=model.window)
        if len(w.y_next) < 30:
            continue
        pred = w.y_curr + model.predict_delta(w.X)
        mae_lstm = float(np.mean(np.abs(pred - w.y_next)))
        mae_pers = float(np.mean(np.abs(w.y_curr - w.y_next)))          # repeat last lap
        mae_slope = float(np.mean(np.abs(w.slope_next - w.y_next)))     # extrapolate trend
        rows.append({
            "round": int(rnd),
            "event": str(race["event_name"].iloc[0])[:26],
            "n": len(w.y_next),
            "lstm": mae_lstm, "persist": mae_pers, "slope": mae_slope,
            "vs_persist_%": 100 * (mae_pers - mae_lstm) / mae_pers,
            "vs_slope_%": 100 * (mae_slope - mae_lstm) / mae_slope,
        })

    t = pd.DataFrame(rows)
    print(t.round(3).to_string(index=False))

    vp, vs = t["vs_persist_%"], t["vs_slope_%"]
    print(f"\nover {len(t)} unseen 2026 races — improvement vs persistence:")
    print(f"  mean   {vp.mean():+.1f}%     median {vp.median():+.1f}%")
    print(f"  spread {vp.min():+.1f}% to {vp.max():+.1f}%   (sd {vp.std():.1f})")
    print(f"  beats persistence in {int((vp > 0).sum())}/{len(t)} races")
    print(f"\nvs rolling-slope baseline: mean {vs.mean():+.1f}%, "
          f"beats it in {int((vs > 0).sum())}/{len(t)} races")

    pooled_l = float(np.average(t["lstm"], weights=t["n"]))
    pooled_p = float(np.average(t["persist"], weights=t["n"]))
    print(f"\npooled over all {int(t['n'].sum())} windows: "
          f"LSTM {pooled_l:.4f} vs persistence {pooled_p:.4f} "
          f"({100 * (pooled_p - pooled_l) / pooled_p:+.1f}%)")
    best = t.loc[vp.idxmax()]
    print(f"\nthe headline single race was the best case: {best['event']} "
          f"at {best['vs_persist_%']:+.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
