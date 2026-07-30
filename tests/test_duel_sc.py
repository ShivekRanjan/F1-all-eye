"""The undercut duel must know a safety car can happen.

It used to model none at all, so it answered a strictly green-flag question
while presenting the answer as the verdict. A neutralisation inside the window
is asymmetric: whoever has *not yet stopped* gets their stop at a discount,
which is exactly how a safety car annihilates an undercut that was working.
"""

from __future__ import annotations

import numpy as np
import pytest

from f1se.sim.duel import CarPlan, car_pit_index, simulate_duel
from f1se.sim.safety_car import SafetyCarModel


def pace(compound: str, age: int, lap: int) -> float:
    base = {"SOFT": 88.0, "MEDIUM": 88.7, "HARD": 89.4}[compound]
    slope = {"SOFT": 0.09, "MEDIUM": 0.055, "HARD": 0.035}[compound]
    return base + slope * age


def test_pit_index_maps_lap_to_window_position():
    p = CarPlan("MEDIUM", 12, 21, "HARD")
    assert car_pit_index(p, 20, 26) == 0      # pits on the first lap of the window
    assert car_pit_index(p, 18, 26) == 2
    assert car_pit_index(p, 21, 26) is None   # stop already behind us
    assert car_pit_index(CarPlan("MEDIUM", 12, None, "HARD"), 20, 26) is None


def _gaps(sc_model):
    you = CarPlan("MEDIUM", 18, 21, "HARD")     # undercut: stop next lap
    rival = CarPlan("MEDIUM", 18, 25, "HARD")   # rival stops later
    return simulate_duel(you, rival, current_lap=20, total_laps=57, pace_fn=pace,
                         gap_s=1.5, end_lap=28, pit_loss_s=21.0,
                         sc_model=sc_model, n_runs=4000, seed=11)


def test_no_model_reproduces_the_old_green_flag_answer():
    a = _gaps(None)
    b = _gaps(SafetyCarModel(prob_per_lap=0.0, vsc_prob_per_lap=0.0, red_prob_per_lap=0.0))
    assert np.mean(a) == pytest.approx(np.mean(b), abs=1e-9)


def test_a_neutralisation_hurts_the_car_that_already_stopped():
    """You pit early; a safety car then gives the rival a discounted stop, so
    your expected gap gets worse. This is the mechanism the tool couldn't see."""
    green = _gaps(None)
    with_sc = _gaps(SafetyCarModel(prob_per_lap=0.10, mean_duration=3,
                                   vsc_prob_per_lap=0.08, vsc_mean_duration=2))
    assert np.mean(with_sc) > np.mean(green), "rival's cheap stop must cost you"


def test_sc_widens_the_outcome_spread():
    """Uncertainty is the product: a possible neutralisation must show up as
    more spread, not just a shifted point estimate."""
    green = _gaps(None)
    with_sc = _gaps(SafetyCarModel(prob_per_lap=0.10, mean_duration=3))
    assert np.std(with_sc) > np.std(green)


def test_red_flag_is_the_cheapest_discount_in_the_duel():
    red = _gaps(SafetyCarModel(prob_per_lap=0.0, red_prob_per_lap=0.10, red_mean_duration=2))
    sc = _gaps(SafetyCarModel(prob_per_lap=0.10, mean_duration=2))
    # A free stop for the rival hurts you more than a merely cheap one.
    assert np.mean(red) > np.mean(sc)


# --- extrapolation guard ------------------------------------------------------
def test_flags_a_tyre_run_past_the_modelled_range():
    """Everywhere else the optimiser is confined to stint lengths the field
    actually ran. A duel takes explicit plans, so it reports instead."""
    from f1se.sim.duel import beyond_modelled_range

    cars = {"rival": CarPlan("MEDIUM", 40, 40, "HARD")}
    out = beyond_modelled_range(cars, current_lap=20, end_lap=28,
                                max_stint={"MEDIUM": 32, "HARD": 43})
    assert len(out) == 1
    assert out[0]["car"] == "rival" and out[0]["compound"] == "MEDIUM"
    assert out[0]["age"] > out[0]["modelled_to"] == 32


def test_a_normal_duel_is_not_flagged():
    from f1se.sim.duel import beyond_modelled_range

    cars = {"you": CarPlan("MEDIUM", 10, 21, "HARD"),
            "rival": CarPlan("MEDIUM", 10, 25, "HARD")}
    assert beyond_modelled_range(cars, 20, 28, {"MEDIUM": 32, "HARD": 43}) == []


def test_no_limits_means_no_claims():
    """Without stint limits we know nothing, so we must assert nothing."""
    from f1se.sim.duel import beyond_modelled_range

    assert beyond_modelled_range({"rival": CarPlan("SOFT", 99, None, "HARD")}, 20, 40, None) == []


def test_peak_age_tracks_both_sides_of_a_stop():
    """A car that pits mid-window ages two compounds, not one."""
    from f1se.sim.duel import peak_tyre_ages

    ages = peak_tyre_ages(CarPlan("MEDIUM", 12, 24, "SOFT"), current_lap=20, end_lap=30)
    assert ages["MEDIUM"] == 16  # 12 + (24 - 20)
    assert ages["SOFT"] == 6     # 30 - 24
