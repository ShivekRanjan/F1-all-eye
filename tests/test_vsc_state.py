"""Three-state neutralisation: green / VSC / full safety car.

The engine used to model track status "4" alone, so a virtual safety car was
invisible — in 2026 that meant seeing 6 of 20 neutralisations, and five races
that had a VSC but no full SC looked entirely event-free. These pin the state
machine and, crucially, the *ordering* of the pit-loss tiers: a stop under VSC
must be cheaper than green and dearer than under a full SC, because the field
never bunches up behind a virtual one.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from f1se.sim.safety_car import (
    VSC_LAP_FACTOR,
    VSC_PIT_LOSS_S,
    SafetyCarModel,
    vsc_laps_in_race,
)
from f1se.sim.simulate import race_totals


def _status(codes_by_lap: dict[int, str], n_drivers: int = 20) -> pd.DataFrame:
    return pd.DataFrame([
        {"year": 2026, "round": 1, "event_name": "Test GP",
         "lap_number": lap, "driver": f"D{i}", "track_status": code}
        for lap, code in codes_by_lap.items() for i in range(n_drivers)
    ])


def test_vsc_laps_detected_and_sc_laps_excluded():
    """A race that escalates VSC -> SC must not count those laps twice."""
    status = _status({1: "1", 2: "6", 3: "6", 4: "4", 5: "4", 6: "1"})
    assert vsc_laps_in_race(status) == [2, 3]          # laps 4-5 are full SC
    assert vsc_laps_in_race(status, exclude_sc=False) == [2, 3]


def test_sample_states_emits_all_three_and_sc_wins_overlap():
    m = SafetyCarModel(prob_per_lap=0.05, mean_duration=3,
                       vsc_prob_per_lap=0.08, vsc_mean_duration=2)
    states = m.sample_states(60, 400, np.random.default_rng(0))
    assert states.shape == (400, 60)
    assert set(np.unique(states)) <= {0, 1, 2}
    assert (states == 1).any() and (states == 2).any(), "both hazards should fire"


def test_no_vsc_hazard_reproduces_two_state_behaviour():
    """An uncalibrated model must behave exactly as before this change."""
    m = SafetyCarModel(prob_per_lap=0.05, mean_duration=3)  # vsc_prob defaults to 0
    states = m.sample_states(50, 200, np.random.default_rng(1))
    assert set(np.unique(states)) <= {0, 2}


def test_pit_loss_tiers_are_ordered_green_vsc_sc():
    """The whole point: VSC sits strictly between green and full SC."""
    laps = 10
    green = np.full((1, laps), 90.0)
    noise = np.zeros((1, laps))
    pit = np.zeros(laps, dtype=bool)
    pit[5] = True  # one stop, on lap 6

    def pit_cost(state_val: int) -> float:
        """Cost of the stop alone, holding the track state fixed.

        Differencing against the same race without a stop is what isolates it —
        a neutralised race is *slower* overall (the neutralised lap itself is
        slower), and the advantage is only ever in the discounted stop.
        """
        states = np.zeros((1, laps), dtype=np.int8)
        states[0, 5] = state_val
        with_pit = race_totals(green, pit, states, noise)[0]
        without = race_totals(green, np.zeros(laps, dtype=bool), states, noise)[0]
        return float(with_pit - without)

    assert VSC_PIT_LOSS_S < 21.0, "a VSC stop must beat a green stop"
    assert VSC_PIT_LOSS_S > 11.0, "a VSC stop must not be as cheap as a full SC"
    assert 1.0 < VSC_LAP_FACTOR < 1.4, "a VSC lap: slower than green, quicker than SC"
    assert pit_cost(0) > pit_cost(1) > pit_cost(2)
    assert pit_cost(0) == pytest.approx(21.0)
    assert pit_cost(1) == pytest.approx(VSC_PIT_LOSS_S)
    assert pit_cost(2) == pytest.approx(11.0)


def test_boolean_mask_still_accepted():
    """Legacy callers passing a boolean SC mask keep working."""
    laps = 8
    green = np.full((2, laps), 95.0)
    noise = np.zeros((2, laps))
    pit = np.zeros(laps, dtype=bool)
    mask = np.zeros((2, laps), dtype=bool)
    mask[:, 3] = True
    out = race_totals(green, pit, mask, noise)
    assert out.shape == (2,)
    assert np.all(out > green.sum(axis=1))  # SC laps are slower than green


@pytest.mark.parametrize("state,factor", [(0, 1.0), (1, VSC_LAP_FACTOR), (2, 1.4)])
def test_lap_time_factor_per_state(state, factor):
    green = np.full((1, 4), 100.0)
    states = np.full((1, 4), state, dtype=np.int8)
    out = race_totals(green, np.zeros(4, dtype=bool), states, np.zeros((1, 4)))
    assert out[0] == pytest.approx(4 * 100.0 * factor)
