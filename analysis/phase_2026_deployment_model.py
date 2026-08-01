"""Should the deployed podium model train on the season it is predicting?

The engine ships one model for two different jobs:

* **Reporting** — must never see the season it is scored on, or the advertised
  AUC is meaningless. Trains on ``year < season``. This is correct and stays.
* **Deployment** — predicting the *next* race. Nothing stops it from learning
  from the 11 rounds of 2026 already in the book, and after a regulation reset
  those rounds are the only ones drawn from the current regime.

Today both jobs use the reporting model, so the live next-race call has never
seen a 2026 race. This measures whether that costs anything.

Walk-forward, which is what deployment actually looks like: to predict round r,
train only on seasons before 2026 **plus 2026 rounds < r**. Never on round r,
never on rounds after it. Round 1 has no prior 2026 data and degenerates to the
current model, as it should.

    python analysis/phase_2026_deployment_model.py
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score

from f1se.config import PROJECT_ROOT
from f1se.standalone.podium import FEATURE_COLS, build_features

SEASON = 2026
PARAMS = dict(n_estimators=200, max_depth=3, learning_rate=0.05, random_state=0)


def _fit(train: pd.DataFrame) -> GradientBoostingClassifier:
    clf = GradientBoostingClassifier(**PARAMS)
    clf.fit(train[FEATURE_COLS], train["podium"])
    return clf


def _hit_at_3(race: pd.DataFrame, score_col: str, *, ascending: bool) -> int:
    top3 = race.sort_values(score_col, ascending=ascending).head(3)
    return int(top3["podium"].sum())


def main() -> int:
    fp = PROJECT_ROOT / "data" / "processed" / "results.parquet"
    results = pd.read_parquet(fp)
    feats = build_features(results, recency_halflife=4.0)

    pre = feats[feats["year"] < SEASON]
    season = feats[feats["year"] == SEASON]
    rounds = sorted(int(r) for r in season["round"].unique())
    print(f"pre-{SEASON} training rows: {len(pre)}   {SEASON} rounds: {len(rounds)}\n")

    base_clf = _fit(pre)  # the current, reporting model — fit once
    rows = []
    for r in rounds:
        race = season[season["round"] == r].copy()
        if race.empty or race["podium"].sum() == 0:
            continue
        prior = season[season["round"] < r]
        train_dep = pd.concat([pre, prior], ignore_index=True)
        dep_clf = _fit(train_dep)

        race["p_report"] = base_clf.predict_proba(race[FEATURE_COLS])[:, 1]
        race["p_deploy"] = dep_clf.predict_proba(race[FEATURE_COLS])[:, 1]
        rows.append({
            "round": r,
            "n_prior_2026": len(prior),
            "report": _hit_at_3(race, "p_report", ascending=False),
            "deploy": _hit_at_3(race, "p_deploy", ascending=False),
            "grid": _hit_at_3(race, "grid", ascending=True),
            "_race": race,
        })

    tbl = pd.DataFrame([{k: v for k, v in r.items() if k != "_race"} for r in rows])
    print(tbl.to_string(index=False))

    allr = pd.concat([r["_race"] for r in rows], ignore_index=True)
    n = len(tbl)
    print(f"\nmean hit@3 over {n} races (out of 3):")
    print(f"  reporting model (never sees {SEASON}) : {tbl['report'].mean():.2f}")
    print(f"  deployment model (walk-forward)      : {tbl['deploy'].mean():.2f}")
    print(f"  naive grid baseline                  : {tbl['grid'].mean():.2f}")
    print("\npooled ROC-AUC:")
    print(f"  reporting  : {roc_auc_score(allr['podium'], allr['p_report']):.4f}")
    print(f"  deployment : {roc_auc_score(allr['podium'], allr['p_deploy']):.4f}")

    diff = tbl["deploy"] - tbl["report"]
    print(f"\nper-race deploy - report: better {int((diff > 0).sum())}, "
          f"worse {int((diff < 0).sum())}, same {int((diff == 0).sum())}")
    # Paired sign test is the honest read on 11 races: a mean gain of a few
    # hundredths over a handful of races is noise, not a result.
    print(f"total podium slots hit: report {tbl['report'].sum()}, "
          f"deploy {tbl['deploy'].sum()}, grid {tbl['grid'].sum()} (of {3 * n})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
