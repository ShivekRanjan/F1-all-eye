"""No-network test for the outcome-predictor orchestration.

Uses the committed results dataset when present (CI has it); skips cleanly if a
checkout lacks it. Verifies the payload shape and JSON-safety, not exact numbers.
"""

from __future__ import annotations

import json

import pytest

from f1se.standalone.outcome import _merge_qualifying, compute_outcome, predict_upcoming


def test_compute_outcome_payload_shape():
    payload = compute_outcome(n_sims=300)
    if payload is None:
        import pytest

        pytest.skip("results.parquet not available in this checkout")

    assert {"test_year", "ongoing", "championship", "model_metrics", "rounds"} <= set(payload)
    assert payload["championship"], "championship list should be non-empty"
    leader = payload["championship"][0]
    assert 0.0 <= leader["win_prob"] <= 1.0 and isinstance(leader["driver"], str)
    assert 0.0 <= payload["model_metrics"]["auc"] <= 1.0
    if payload["rounds"]:
        pred = payload["rounds"][0]["predictions"][0]
        assert {"driver", "team", "grid", "podium_prob", "actual"} <= set(pred)
    json.dumps(payload)  # must be JSON-serialisable for the API


def test_predict_upcoming_next_round():
    # use_qualifying=False keeps this offline and deterministic: the auto-fed
    # grid depends on whether qualifying has run in the real world.
    payload = predict_upcoming(use_qualifying=False)
    if payload is None:
        pytest.skip("results.parquet not available in this checkout")

    assert payload["grid_source"] == "form"
    assert payload["next_round"] >= 2 and payload["predictions"]
    top = payload["predictions"][0]
    assert {"driver", "team", "grid", "podium_prob"} <= set(top)
    assert 0.0 <= top["podium_prob"] <= 1.0
    # best-first ordering
    probs = [p["podium_prob"] for p in payload["predictions"]]
    assert probs == sorted(probs, reverse=True)
    # a custom grid override changes the outcome (put the last driver on pole)
    last = payload["predictions"][-1]["driver"]
    bumped = predict_upcoming(grid={last: 1}, use_qualifying=False)
    by_driver = {p["driver"]: p for p in bumped["predictions"]}
    assert by_driver[last]["grid"] == 1
    assert bumped["grid_source"] == "custom"
    json.dumps(payload)


# --- auto-fed qualifying grid -------------------------------------------------
def test_merge_qualifying_uses_real_positions():
    """Drivers who qualified get their true position, not a re-ranked one."""
    form = {"AAA": 1, "BBB": 2, "CCC": 3}
    quali = {"CCC": 1, "AAA": 2, "BBB": 3}
    assert _merge_qualifying(form, quali) == {"CCC": 1, "AAA": 2, "BBB": 3}


def test_merge_qualifying_parks_unqualified_behind_the_field():
    """A driver with form but no qualifying classification lines up last,
    ordered among other such drivers by form — never ahead of the grid."""
    form = {"AAA": 1, "BBB": 2, "CCC": 3, "DDD": 4}
    merged = _merge_qualifying(form, {"CCC": 1, "AAA": 2})
    assert merged["CCC"] == 1 and merged["AAA"] == 2
    assert merged["BBB"] == 3 and merged["DDD"] == 4  # behind, form order kept
    assert max(merged.values()) == 4 and len(set(merged.values())) == 4


def test_merge_qualifying_ignores_unknown_drivers():
    """Qualifying entries we have no season form for can't be predicted on, so
    they're dropped rather than injected with null features."""
    merged = _merge_qualifying({"AAA": 1}, {"ZZZ": 1, "AAA": 2})
    assert merged == {"AAA": 2}
    assert _merge_qualifying({"AAA": 1}, {"ZZZ": 1}) is None  # nothing usable


@pytest.mark.network
def test_predict_upcoming_auto_feeds_qualifying():
    """Once qualifying has run for the next round, the grid comes from it."""
    payload = predict_upcoming()
    if payload is None:
        pytest.skip("results.parquet not available in this checkout")
    assert payload["grid_source"] in {"form", "qualifying"}
    if payload["grid_source"] == "qualifying":
        grids = [p["grid"] for p in payload["predictions"]]
        assert len(set(grids)) == len(grids), "grid positions must be unique"
        assert min(grids) == 1
