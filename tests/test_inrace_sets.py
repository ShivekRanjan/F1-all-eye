"""Mid-race tyre-set accounting.

Sets burned earlier in *this* race count against the allowance, which makes the
in-race constraint stricter than the pre-race one. It relies on the full stint
history: `compounds_used` is the distinct set (it answers the two-compound
rule) and collapses a second run on the same compound — exactly the information
set counting needs.
"""

from __future__ import annotations

from f1se.sim.inrace import RaceState, enumerate_remaining

LIMITS = {"SOFT": 2, "MEDIUM": 2, "HARD": 2}


def _state(**kw):
    base = dict(total_laps=57, current_lap=20, current_compound="MEDIUM",
                tyre_age=12, compounds_used=("MEDIUM", "HARD"))
    base.update(kw)
    return RaceState(**base)


def test_spent_sets_count_against_the_allowance():
    """Two MEDIUM sets already gone means no plan may fit another."""
    s = _state(stints_used=("MEDIUM", "HARD", "MEDIUM"))
    plans = enumerate_remaining(s, max_future_stops=2, min_stint=6,
                                pit_grid_step=4, max_sets=LIMITS)
    assert plans
    assert all("MEDIUM" not in p.future_compounds for p in plans)


def test_unspent_compound_is_still_offered():
    s = _state(stints_used=("MEDIUM",), compounds_used=("MEDIUM",))
    plans = enumerate_remaining(s, max_future_stops=2, min_stint=6,
                                pit_grid_step=4, max_sets=LIMITS)
    assert any("HARD" in p.future_compounds for p in plans)
    assert any("MEDIUM" in p.future_compounds for p in plans)


def test_unknown_history_leaves_the_limit_unenforced():
    """Without a stint history we'd be counting sets from the distinct list,
    which undercounts. Better to not enforce than to enforce a wrong number."""
    s = _state(stints_used=())
    with_limits = enumerate_remaining(s, max_future_stops=2, min_stint=6,
                                      pit_grid_step=4, max_sets=LIMITS)
    without = enumerate_remaining(s, max_future_stops=2, min_stint=6, pit_grid_step=4)
    assert len(with_limits) == len(without)


def test_two_compound_rule_still_holds_alongside_set_limits():
    s = _state(stints_used=("MEDIUM",), compounds_used=("MEDIUM",))
    plans = enumerate_remaining(s, max_future_stops=2, min_stint=6,
                                pit_grid_step=4, max_sets=LIMITS)
    for p in plans:
        whole_race = {"MEDIUM"} | set(p.future_compounds)
        assert len(whole_race) >= 2, "a one-compound race is illegal"
