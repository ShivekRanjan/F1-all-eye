"""Outcome predictor orchestration — championship projection + per-race podium.

Assembles the standalone championship simulator and the podium classifier into a
single JSON-friendly payload for the API. Kept here, not in the API layer, so
it's reusable and tested in one place.
"""

from __future__ import annotations

import time
from functools import lru_cache
from pathlib import Path

import pandas as pd

from f1se.config import PROJECT_ROOT
from f1se.standalone.championship import predict_season, project_ongoing_season
from f1se.standalone.podium import build_features, predict_race, train_podium_model


def _resolve_results(data_dir: str | Path | None) -> Path | None:
    candidates = []
    if data_dir is not None:
        candidates.append(Path(data_dir) / "results.parquet")
    candidates += [Path.cwd() / "data" / "processed" / "results.parquet",
                   PROJECT_ROOT / "data" / "processed" / "results.parquet"]
    for c in candidates:
        if c.exists():
            return c
    return None


def _f(x) -> float | None:
    return None if pd.isna(x) else float(x)


def compute_outcome(data_dir: str | Path | None = None, *, n_sims: int = 5000) -> dict | None:
    """Build the full outcome payload, or ``None`` if the results dataset is absent.

    Trains the podium model with a forward holdout on the latest season, projects
    (or simulates) the title race, and returns per-round podium predictions with
    the actual podium flagged.
    """
    fp = _resolve_results(data_dir)
    if fp is None:
        return None
    results = pd.read_parquet(fp)
    # Recency-weight form (halflife ~4 races) so a team's mid-season upgrade step
    # shows up quickly instead of being diluted by a flat window.
    feats = build_features(results, recency_halflife=4.0)
    test_year = int(results["year"].max())
    model = train_podium_model(feats, test_year=test_year)

    full = int(results.groupby("year")["round"].nunique().max())
    done = int(results[results["year"] == test_year]["round"].nunique())
    ongoing = done < full - 2
    if ongoing:
        # Start the projection from the official points — incl. sprint races.
        from f1se.standalone.standings import _sprint_sums, load_sprints

        extra = _sprint_sums(load_sprints(fp), test_year, "driver")
        champ = project_ongoing_season(results, test_year, total_races=full,
                                       n_sims=n_sims, extra_points=extra)
    else:
        champ = predict_season(results, test_year, n_sims=n_sims)

    has_points = "points" in champ.columns
    championship = [
        {"driver": str(r.driver), "win_prob": _f(r.win_prob),
         "points": _f(r.points) if has_points else None}
        for r in champ.head(8).itertuples(index=False)
    ]

    test = feats[feats["year"] == test_year]
    rounds_out = []
    for rnd in sorted(test["round"].unique()):
        race = test[test["round"] == rnd]
        pred = predict_race(model, race).head(8)
        podium = set(race[race["podium"] == 1]["driver"])
        rounds_out.append({
            "round": int(rnd),
            "event_name": str(race["event_name"].iloc[0]),
            "predictions": [
                {"driver": str(p.driver), "team": str(p.team), "grid": int(p.grid),
                 "podium_prob": _f(p.podium_prob), "actual": bool(p.driver in podium)}
                for p in pred.itertuples(index=False)
            ],
        })

    mtr = model.metrics
    return {
        "test_year": test_year, "ongoing": ongoing, "done": done, "full": full,
        "championship": championship,
        "model_metrics": {
            "auc": _f(mtr["auc"]),
            "model_precision_at_3": _f(mtr["model_precision_at_3"]),
            "grid_baseline_precision_at_3": _f(mtr["grid_baseline_precision_at_3"]),
        },
        "rounds": rounds_out,
    }


@lru_cache(maxsize=1)
def cached_outcome() -> dict | None:
    """Process-wide cached outcome payload (heavy: trains a model + Monte Carlo)."""
    return compute_outcome()


# --------------------------------------------------------------------------- #
# Predicting the NEXT (not-yet-raced) round — a real forward prediction.       #
# The podium model is grid + form only (no circuit feature), and an upcoming   #
# race has no grid until qualifying, so the grid defaults to each driver's     #
# current qualifying form and is overridable. Form is grid-independent, so it  #
# is computed once (cached) and only the grid varies per call — fast enough    #
# to re-predict live as the user edits the grid.                               #
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _upcoming_context() -> dict | None:
    fp = _resolve_results(None)
    if fp is None:
        return None
    results = pd.read_parquet(fp)
    season = int(results["year"].max())
    done = results[results["year"] == season]
    if done.empty:
        return None
    next_round = int(done["round"].max()) + 1

    # Default grid = each driver's average grid so far (their qualifying form), ranked.
    avg_grid = done.groupby("driver", observed=True)["grid"].mean().sort_values()
    default_grid = {str(d): i + 1 for i, d in enumerate(avg_grid.index)}
    team = (done.sort_values("round").groupby("driver", observed=True).tail(1)
            .set_index("driver")["team"])

    rows = [{
        "year": season, "round": next_round, "event_name": "Next Race", "driver": d,
        "team": str(team.get(d, "")), "grid": float(default_grid[d]),
        "position": float("nan"), "points": float("nan"), "status": "Finished",
    } for d in default_grid]
    feats = build_features(pd.concat([results, pd.DataFrame(rows)], ignore_index=True),
                           recency_halflife=4.0)
    model = train_podium_model(feats, test_year=season)   # trains on < season only
    nxt = feats[(feats["year"] == season) & (feats["round"] == next_round)]
    return {
        "season": season, "next_round": next_round, "default_grid": default_grid,
        "clf": model.clf, "feature_cols": list(model.feature_cols),
        "rows": nxt[["driver", "team", *model.feature_cols]].reset_index(drop=True),
    }


def _qualifying_grid(season: int, rnd: int) -> dict[str, int] | None:
    """The round's actual starting order, from FastF1's qualifying classification.

    Best-effort and network-bound: returns ``None`` when qualifying hasn't run
    yet (the normal case for most of a race week) or FastF1 is unreachable, so
    the caller falls back to form. Qualifying classification is the best
    *pre-race* proxy for the grid — it can't know about post-qualifying grid
    penalties or pit-lane starts, which the UI states rather than glosses over.
    """
    try:
        from f1se.config import enable_cache

        enable_cache()
        import fastf1

        s = fastf1.get_session(int(season), int(rnd), "Q")
        # laps + race-control messages are both required: for a session this
        # recent, Ergast has nothing, so FastF1 derives the classification from
        # lap times — and it refuses to do that without the messages that say
        # which laps were deleted. The lighter load used elsewhere returns an
        # entry list with an all-NaN Position column, which looks like success.
        s.load(laps=True, telemetry=False, weather=False, messages=True)
        res = s.results
    except Exception:  # pragma: no cover - network / qualifying not run yet
        return None
    if res is None or len(res) == 0:
        return None
    out: dict[str, int] = {}
    for row in res.itertuples(index=False):
        code = str(getattr(row, "Abbreviation", "") or "").strip()
        pos = pd.to_numeric(getattr(row, "Position", None), errors="coerce")
        if code and pd.notna(pos):
            out[code] = int(pos)
    return out or None


# TTL cache, not lru_cache: qualifying *happens* partway through a race week, so
# caching the pre-quali miss forever would defeat the whole point. Misses are
# deliberately not cached (retry on the next call, like schedule.py); only a
# real classification is held, and only for 15 minutes so a post-quali penalty
# correction lands promptly.
_QGRID_TTL_S = 900
_QGRID_CACHE: dict[tuple[int, int], tuple[float, dict[str, int]]] = {}


def _cached_qualifying_grid(season: int, rnd: int) -> dict[str, int] | None:
    key = (int(season), int(rnd))
    hit = _QGRID_CACHE.get(key)
    if hit is not None and time.time() - hit[0] < _QGRID_TTL_S:
        return hit[1]
    grid = _qualifying_grid(season, rnd)
    if grid:  # don't cache a miss — quali may run minutes from now
        _QGRID_CACHE[key] = (time.time(), grid)
    return grid


def _merge_qualifying(form_grid: dict[str, int], quali: dict[str, int]) -> dict[str, int] | None:
    """Real qualifying positions for drivers we have season form for.

    A driver with no qualifying classification (DNS, or an entry absent from the
    results dataset) keeps their form ranking but lines up behind the whole
    qualified field — the honest placement for "we don't know where they start".
    """
    known = {d: p for d, p in quali.items() if d in form_grid}
    if not known:
        return None
    tail = max(known.values())
    rest = sorted((d for d in form_grid if d not in known), key=lambda d: form_grid[d])
    out = dict(known)
    for i, d in enumerate(rest):
        out[d] = tail + 1 + i
    return out


def predict_upcoming(
    grid: dict[str, int] | None = None, *, use_qualifying: bool = True
) -> dict | None:
    """Predict the next round's podium probabilities from current form.

    The baseline grid is the real qualifying order once FastF1 has it, and each
    driver's qualifying *form* before that — so the call sharpens by itself as
    the weekend progresses, with no manual step. ``grid`` overrides start
    positions on top of that baseline (``{driver: grid_pos}``); any driver not
    listed keeps the baseline. Returns drivers best-first.

    ``use_qualifying=False`` keeps it purely offline (used by the no-network
    tests, and available if you deliberately want the pre-quali projection).
    """
    ctx = _upcoming_context()
    if ctx is None:
        return None
    baseline, source = dict(ctx["default_grid"]), "form"
    if use_qualifying:
        real = _cached_qualifying_grid(ctx["season"], ctx["next_round"])
        merged = _merge_qualifying(baseline, real) if real else None
        if merged:
            baseline, source = merged, "qualifying"
    used = {**baseline, **{str(k): int(v) for k, v in (grid or {}).items()}}
    rows = ctx["rows"].copy()
    rows["grid"] = rows["driver"].map(lambda d: float(used.get(str(d), 20)))
    rows["podium_prob"] = ctx["clf"].predict_proba(rows[ctx["feature_cols"]])[:, 1]
    rows = rows.sort_values("podium_prob", ascending=False)
    return {
        "season": ctx["season"], "next_round": ctx["next_round"],
        "grid_source": "custom" if grid else source,
        "predictions": [
            {"driver": str(r.driver), "team": str(r.team), "grid": int(r.grid),
             "podium_prob": _f(r.podium_prob)}
            for r in rows.itertuples(index=False)
        ],
    }
