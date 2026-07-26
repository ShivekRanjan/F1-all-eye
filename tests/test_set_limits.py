"""Tyre-set feasibility: a stint needs a fresh set, and sets are finite.

The optimiser knew stint *length* limits but nothing about how many sets a team
has. Nothing stopped it proposing a plan that reuses one compound more often
than any team has ever managed — a plan that cannot be fielded is not a
recommendation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from f1se.eda import compound_set_limits
from f1se.sim.optimize import enumerate_strategies


def _laps(rows):
    return pd.DataFrame(rows)


def test_set_limits_read_off_observed_running():
    """One driver ran MEDIUM twice and HARD once; limits should reflect that."""
    clean = _laps([
        {"year": 2026, "round": 1, "driver": "AAA", "stint": 1, "compound": "MEDIUM"},
        {"year": 2026, "round": 1, "driver": "AAA", "stint": 2, "compound": "HARD"},
        {"year": 2026, "round": 1, "driver": "AAA", "stint": 3, "compound": "MEDIUM"},
    ])
    limits = compound_set_limits(clean)
    assert limits["MEDIUM"] == 2
    assert limits["HARD"] == 1


def test_limits_are_never_below_one():
    clean = _laps([{"year": 2026, "round": 1, "driver": "AAA", "stint": 1, "compound": "SOFT"}])
    assert compound_set_limits(clean)["SOFT"] >= 1


def test_candidates_respect_the_set_limit():
    """With one HARD set available, no plan may use HARD twice."""
    cands = enumerate_strategies(
        total_laps=60, compounds=("SOFT", "MEDIUM", "HARD"), max_stops=3,
        min_stint=10, pit_grid_step=6, max_sets={"HARD": 1, "MEDIUM": 2, "SOFT": 2},
    )
    assert cands, "constraint must not empty the candidate space"
    for s in cands:
        assert s.compounds.count("HARD") <= 1
        assert s.compounds.count("MEDIUM") <= 2
        assert s.compounds.count("SOFT") <= 2


def test_without_limits_reuse_is_still_allowed():
    """The constraint is opt-in; omitting it preserves the old behaviour."""
    unbounded = enumerate_strategies(
        total_laps=60, compounds=("SOFT", "HARD"), max_stops=3,
        min_stint=10, pit_grid_step=6,
    )
    assert any(s.compounds.count("HARD") >= 3 for s in unbounded)


def test_limit_shrinks_the_search_space_but_keeps_the_two_compound_rule():
    kw = dict(total_laps=60, compounds=("SOFT", "MEDIUM", "HARD"), max_stops=3,
              min_stint=10, pit_grid_step=6)
    loose = enumerate_strategies(**kw)
    tight = enumerate_strategies(**kw, max_sets={"SOFT": 1, "MEDIUM": 1, "HARD": 1})
    assert 0 < len(tight) < len(loose)
    # Every surviving plan still uses at least two distinct compounds.
    assert all(len(set(s.compounds)) >= 2 for s in tight)
