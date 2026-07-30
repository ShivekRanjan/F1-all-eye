"""Two-car undercut / overcut duel — "should I pit now to jump my rival?"

The single most-asked F1 strategy question, and the one a single-car simulator
can't answer. This models the *undercut mechanic* exactly: pit earlier than a
rival, gain fresh-tyre pace while they stay out on worn rubber, and see whether
that pace gain plus the gap beats the pit-loss before they respond.

It is deliberately a **cumulative-time (free-air) model**: it tells you the time
delta of the undercut, i.e. who is ahead on the clock once both cars have
stopped. It does NOT model dirty air or whether you can physically pass — a real
caveat surfaced to the user, not hidden. It reuses the same per-lap pace function
(degradation + fuel + cliff) as the rest of the engine.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from f1se.sim.safety_car import RED_PIT_LOSS_S, VSC_PIT_LOSS_FRACTION, SafetyCarModel
from f1se.sim.simulate import PaceFn


@dataclass(frozen=True)
class CarPlan:
    """One car's tyre state now + its single upcoming stop."""

    compound: str            # tyre currently fitted
    tyre_age: int            # its age now
    pit_lap: int | None      # lap of the upcoming stop (None = no stop in window)
    new_compound: str        # tyre fitted at that stop
    pace_offset_s: float = 0.0   # intrinsic per-lap pace vs the rival (+ = slower)


def car_lap_times(plan: CarPlan, current_lap: int, end_lap: int,
                  pace_fn: PaceFn, pit_loss_s: float) -> np.ndarray:
    """Deterministic green lap times for one car, laps current_lap+1..end_lap."""
    has_pit = plan.pit_lap is not None and plan.pit_lap > current_lap
    out = []
    for lap in range(current_lap + 1, end_lap + 1):
        if has_pit and lap > plan.pit_lap:           # fresh tyre after the stop
            comp, age = plan.new_compound, lap - plan.pit_lap
        else:                                        # ongoing tyre, still ageing
            comp, age = plan.compound, plan.tyre_age + (lap - current_lap)
        t = pace_fn(comp, age, lap) + plan.pace_offset_s
        if has_pit and lap == plan.pit_lap:          # in-lap pays the pit loss
            t += pit_loss_s
        out.append(t)
    return np.array(out, dtype=float)


def car_pit_index(plan: CarPlan, current_lap: int, end_lap: int) -> int | None:
    """Index into the lap window where this car's stop falls, if it does."""
    if plan.pit_lap is None or not (current_lap < plan.pit_lap <= end_lap):
        return None
    return plan.pit_lap - current_lap - 1


def peak_tyre_ages(plan: CarPlan, current_lap: int, end_lap: int) -> dict[str, int]:
    """Oldest each compound gets over the window, per compound."""
    ages: dict[str, int] = {}
    has_pit = plan.pit_lap is not None and plan.pit_lap > current_lap
    for lap in range(current_lap + 1, end_lap + 1):
        if has_pit and lap > plan.pit_lap:
            comp, age = plan.new_compound, lap - plan.pit_lap
        else:
            comp, age = plan.compound, plan.tyre_age + (lap - current_lap)
        ages[comp] = max(ages.get(comp, 0), age)
    return ages


def beyond_modelled_range(
    cars: dict[str, CarPlan], current_lap: int, end_lap: int,
    max_stint: dict[str, int] | None,
) -> list[dict]:
    """Where this duel asks the pace model to extrapolate past its evidence.

    Everywhere else the engine refuses to run a tyre older than the field
    actually ran it (:func:`f1se.eda.compound_stint_limits`) — the cliff is
    censored out of race data, so a linear fit has no support beyond the
    observed range and reads far too gentle out there (METHODOLOGY §3).

    The duel takes explicit plans rather than enumerating them, so there is
    nothing to constrain: the user can legitimately ask "what if my rival
    stays out ten more laps?" and that is the whole point of the tool. Clamping
    would silently answer a different question. So it answers the one asked and
    says where the answer stops being evidence-backed — which matters because
    the error is *directional*: understated degradation always flatters the car
    staying out, i.e. it biases against the undercut.
    """
    if not max_stint:
        return []
    out: list[dict] = []
    for who, plan in cars.items():
        for comp, age in peak_tyre_ages(plan, current_lap, end_lap).items():
            limit = max_stint.get(comp)
            if limit is not None and age > limit:
                out.append({"car": who, "compound": comp, "age": int(age),
                            "modelled_to": int(limit)})
    return out


def simulate_duel(you: CarPlan, rival: CarPlan, *, current_lap: int, total_laps: int,
                  pace_fn: PaceFn, gap_s: float, end_lap: int | None = None,
                  pit_loss_s: float = 21.0, pace_noise_s: float = 0.3,
                  sc_model: SafetyCarModel | None = None,
                  n_runs: int = 2000, seed: int = 0) -> np.ndarray:
    """Gap (s) to the rival at ``end_lap`` (default the flag); positive = behind.

    ``gap_s`` is your current deficit (positive = rival ahead of you now). For an
    undercut, evaluate at the *crossover* (shortly after both have pitted), not
    the flag — otherwise an early stop is unfairly judged on a worn end-of-race tyre.
    """
    end_lap = end_lap or total_laps
    you_det = car_lap_times(you, current_lap, end_lap, pace_fn, pit_loss_s)
    riv_det = car_lap_times(rival, current_lap, end_lap, pace_fn, pit_loss_s)
    rng = np.random.default_rng(seed)
    n_laps = len(you_det)
    you_tot = (you_det + rng.normal(0, pace_noise_s, (n_runs, n_laps))).sum(axis=1)
    riv_tot = (riv_det + rng.normal(0, pace_noise_s, (n_runs, n_laps))).sum(axis=1)

    if sc_model is not None:
        # A neutralisation inside the window is the single biggest thing that can
        # decide an undercut, and it is *asymmetric*: whoever has not yet stopped
        # gets their stop at a discount, which is exactly how a safety car
        # annihilates an undercut that was working. Both cars are scored against
        # the SAME sampled races (common random numbers), so the comparison stays
        # paired — the noise draws above already follow that discipline.
        states = sc_model.sample_states(n_laps, n_runs, rng)
        for plan, totals in ((you, you_tot), (rival, riv_tot)):
            idx = car_pit_index(plan, current_lap, end_lap)
            if idx is None:
                continue
            st = states[:, idx]
            discounted = np.select(
                [st == 3, st == 2, st == 1],
                [RED_PIT_LOSS_S, pit_loss_s * 0.5,
                 pit_loss_s * VSC_PIT_LOSS_FRACTION], pit_loss_s)
            # car_lap_times already charged full green pit loss on the in-lap.
            totals += discounted - pit_loss_s
        # Neutralised laps are slower for *both* cars, so they cancel in a gap
        # comparison; only the pit-loss discount is asymmetric and modelled.

    return gap_s + (you_tot - riv_tot)               # + = still behind at the flag


def undercut_decision(
    *, current_lap: int, total_laps: int, pace_fn: PaceFn, gap_s: float,
    your_compound: str, your_age: int, your_new_compound: str,
    rival_compound: str, rival_age: int, rival_new_compound: str, rival_pit_lap: int,
    your_pace_offset_s: float = 0.0, pit_loss_s: float = 21.0, settle_laps: int = 3,
    pace_noise_s: float = 0.3, sc_model: SafetyCarModel | None = None,
    max_stint: dict[str, int] | None = None,
    n_runs: int = 2000, seed: int = 0,
) -> dict:
    """Compare pitting NOW (undercut) vs covering the rival (pit on the same lap).

    Judged at the *crossover* — ``settle_laps`` after the rival's stop, when both
    cars are on fresh tyres and track position is decided. Returns each option's
    expected gap there and P(you end ahead), plus a verdict.
    """
    rival = CarPlan(rival_compound, rival_age, rival_pit_lap, rival_new_compound)
    horizon = min(total_laps, rival_pit_lap + settle_laps)

    def _eval(your_pit: int) -> dict:
        you = CarPlan(your_compound, your_age, your_pit, your_new_compound, your_pace_offset_s)
        gaps = simulate_duel(you, rival, current_lap=current_lap, total_laps=total_laps,
                             pace_fn=pace_fn, gap_s=gap_s, end_lap=horizon, pit_loss_s=pit_loss_s,
                             pace_noise_s=pace_noise_s, sc_model=sc_model,
                             n_runs=n_runs, seed=seed)
        return {"final_gap_s": float(np.mean(gaps)), "p_ahead": float(np.mean(gaps < 0))}

    undercut = _eval(current_lap + 1)                # pit on the next lap
    cover = _eval(rival_pit_lap)                     # pit when the rival does
    gain = cover["final_gap_s"] - undercut["final_gap_s"]   # +ve = undercut is faster
    works = undercut["final_gap_s"] < cover["final_gap_s"] and undercut["p_ahead"] > cover["p_ahead"]

    # Deterministic lap-by-lap gap path for each option, so the UI can *show*
    # the crossover instead of only describing it (people read a line crossing
    # zero instantly; a textual "gains 1.4s" has to be mentally simulated).
    def _path(your_pit: int) -> list[float]:
        you = CarPlan(your_compound, your_age, your_pit, your_new_compound, your_pace_offset_s)
        yd = car_lap_times(you, current_lap, horizon, pace_fn, pit_loss_s)
        rd = car_lap_times(rival, current_lap, horizon, pace_fn, pit_loss_s)
        return [round(g, 3) for g in (gap_s + np.cumsum(yd - rd))]

    trajectory = {
        "laps": list(range(current_lap + 1, horizon + 1)),
        "undercut": _path(current_lap + 1),
        "cover": _path(rival_pit_lap),
        "your_pit_lap": current_lap + 1,
        "rival_pit_lap": rival_pit_lap,
    }
    # Both options are checked: the undercut runs YOUR tyre short and the
    # rival's long, the cover does the reverse, so they strain the model at
    # opposite ends and either can be the one that leaves its evidence.
    extrapolated = beyond_modelled_range(
        {"you": CarPlan(your_compound, your_age, current_lap + 1, your_new_compound),
         "rival": rival},
        current_lap, horizon, max_stint,
    )
    return {
        "undercut": undercut,
        "cover": cover,
        "undercut_gain_s": gain,
        "undercut_works": works,
        "trajectory": trajectory,
        "beyond_modelled_range": extrapolated,
        "verdict": (
            f"Undercut now — it gains ~{gain:.1f}s on the rival and "
            f"ends ahead {undercut['p_ahead']*100:.0f}% of the time."
            if works else
            f"Hold / cover — undercutting gains only {gain:+.1f}s; "
            f"pitting with the rival ends ahead {cover['p_ahead']*100:.0f}% of the time."
        ),
    }
