"""Phase 3 — safety-car hazard model.

A safety car (SC) bunches the field and makes a pit stop much cheaper (everyone
is already slow), so SC timing is the single biggest source of strategy
uncertainty. We model it as a simple per-lap hazard: each racing lap can *trigger*
an SC with probability ``prob_per_lap``, and an SC then lasts ``mean_duration``
laps. Sampling many races gives the distribution of SC scenarios the simulator
rolls strategies against.

Defaults are literature-ballpark (~0.6–0.8 SC periods per race); they can be
recalibrated from data later via :meth:`SafetyCarModel.from_rate`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# FastF1 track-status codes (they can concatenate within one lap's string).
SC_CODE = "4"           # full safety car — field bunches behind the pace car
VSC_CODES = ("6", "7")  # virtual safety car: 6 = deployed, 7 = ending

# Regulation-derived pit-loss tiers. Under a *full* SC the field bunches, so the
# time surrendered by pitting collapses (~12-14 s vs ~20-25 s green). A VSC slows
# every car against a delta but never closes the pack up, so a stop there is
# cheaper than green but dearer than under SC (~15-18 s). Treating the two as one
# state — which this engine did until the VSC was found to be uncounted entirely
# — either ignores a real cheap-stop window or over-credits it.
VSC_PIT_LOSS_S = 16.0   # midpoint of the observed 15-18 s band
VSC_LAP_FACTOR = 1.35   # VSC delta is marginally quicker than following the SC

RED_CODE = "5"          # race suspended
# A red flag is not a slower lap — it is a *suspension*. Sporting Regulations
# Art. 57 lets teams work on a stopped car in the pit lane, explicitly including
# "changing wheels and tyres", so the stop costs essentially nothing. That is the
# single largest discount in the sport and the engine modelled none of it.
# The lap factor stays 1.0 deliberately: the suspension itself is dead time that
# every strategy serves equally, so it cancels in a between-strategy comparison,
# whereas the free tyre change does not.
RED_PIT_LOSS_S = 0.0
RED_LAP_FACTOR = 1.0


@dataclass(frozen=True)
class SafetyCarModel:
    """Per-lap safety-car hazard.

    Attributes
    ----------
    prob_per_lap
        Probability an SC is triggered on any given racing lap.
    mean_duration
        Number of laps an SC stays out once triggered.
    """

    prob_per_lap: float = 0.013
    mean_duration: int = 4
    # Virtual safety car, modelled as its own state rather than folded into the
    # SC hazard. Zero keeps the old two-state behaviour for callers that predate
    # this (and for the deterministic no-SC path).
    vsc_prob_per_lap: float = 0.0
    vsc_mean_duration: int = 3
    # Race suspension. Rare (~1 race in 10) but decisive when it lands, because
    # the tyre change is free — see RED_PIT_LOSS_S.
    red_prob_per_lap: float = 0.0
    red_mean_duration: int = 1

    @classmethod
    def from_rate(cls, sc_periods_per_race: float, total_laps: int, mean_duration: int = 4):
        """Build from an expected number of SC periods per race of ``total_laps``."""
        return cls(prob_per_lap=sc_periods_per_race / total_laps, mean_duration=mean_duration)

    @classmethod
    def from_track_status(cls, status: pd.DataFrame) -> SafetyCarModel:
        """Calibrate both hazards from observed per-lap ``track_status`` data.

        ``status`` needs columns ``year, round, lap_number, track_status`` (one
        row per driver-lap, unfiltered). Replaces the literature default with the
        measured per-lap trigger rate and mean duration; see
        :func:`safety_car_summary` for the diagnostics behind it.

        The VSC rate is measured separately and from *VSC-only* laps, so a race
        that ran both doesn't get double-counted.
        """
        summary = safety_car_summary(status)
        prob = summary["n_periods"] / summary["total_race_laps"]
        vsc = vsc_summary(status)
        red = red_flag_summary(status)
        return cls(
            prob_per_lap=float(prob),
            mean_duration=int(round(summary["mean_duration"])),
            vsc_prob_per_lap=float(vsc["n_periods"] / vsc["total_race_laps"])
            if vsc["total_race_laps"] else 0.0,
            vsc_mean_duration=max(1, int(round(vsc["mean_duration"] or 3))),
            red_prob_per_lap=float(red["n_periods"] / red["total_race_laps"])
            if red["total_race_laps"] else 0.0,
            red_mean_duration=max(1, int(round(red["mean_duration"] or 1))),
        )

    def _active(self, prob: float, duration: int, total_laps: int,
                n_runs: int, rng: np.random.Generator) -> np.ndarray:
        triggers = rng.random((n_runs, total_laps)) < prob
        D = max(1, int(duration))
        csum = np.cumsum(triggers.astype(np.int32), axis=1)
        shifted = np.zeros_like(csum)
        if D < total_laps:
            shifted[:, D:] = csum[:, :-D]
        return (csum - shifted) > 0

    def sample_states(self, total_laps: int, n_runs: int,
                      rng: np.random.Generator) -> np.ndarray:
        """``(n_runs, total_laps)`` int8: 0 green, 1 VSC, 2 full SC, 3 red flag.

        Hazards are drawn independently and resolved by severity, so an incident
        that escalates counts once and the most severe condition governs both lap
        time and pit loss: red flag > full SC > VSC.
        """
        sc = self._active(self.prob_per_lap, self.mean_duration, total_laps, n_runs, rng)
        states = np.zeros((n_runs, total_laps), dtype=np.int8)
        if self.vsc_prob_per_lap > 0:
            vsc = self._active(self.vsc_prob_per_lap, self.vsc_mean_duration,
                               total_laps, n_runs, rng)
            states[vsc] = 1
        states[sc] = 2
        if self.red_prob_per_lap > 0:
            red = self._active(self.red_prob_per_lap, self.red_mean_duration,
                               total_laps, n_runs, rng)
            states[red] = 3
        return states

    def sample_mask(self, total_laps: int, n_runs: int, rng: np.random.Generator) -> np.ndarray:
        """Return a boolean ``(n_runs, total_laps)`` mask of laps run under SC.

        A trigger on lap ``l`` puts laps ``l .. l+mean_duration-1`` under SC
        (overlapping triggers simply merge).
        """
        triggers = rng.random((n_runs, total_laps)) < self.prob_per_lap
        D = max(1, int(self.mean_duration))
        csum = np.cumsum(triggers.astype(np.int32), axis=1)
        shifted = np.zeros_like(csum)
        if D < total_laps:
            shifted[:, D:] = csum[:, :-D]
        # Number of triggers in the trailing D-lap window; >0 => SC active.
        return (csum - shifted) > 0


def calibrate_per_track(
    status: pd.DataFrame, *, shrinkage_laps: float = 150.0
) -> dict[str, SafetyCarModel]:
    """Per-circuit calibrated SC models, shrunk toward the global rate.

    With only ~2 races per track, a raw per-track hazard is noisy (a track with
    no observed SC isn't truly zero-probability). We partially pool: the per-lap
    hazard is a weighted blend of the track's own rate and the global rate, with
    ``shrinkage_laps`` of "global prior" laps. More observed laps -> more trust in
    the track's own data.
    """
    glob = safety_car_summary(status)
    global_prob = glob["n_periods"] / glob["total_race_laps"] if glob["total_race_laps"] else 0.0
    global_dur = glob["mean_duration"] or 4.0
    # The VSC hazard is shrunk on exactly the same footing — these are the models
    # the engine actually uses per circuit, so leaving VSC out here would have
    # confined the fix to the global fallback path.
    gv = vsc_summary(status)
    global_vprob = gv["n_periods"] / gv["total_race_laps"] if gv["total_race_laps"] else 0.0
    global_vdur = gv["mean_duration"] or 3.0
    # Red flags are rare enough (~8 in 81 races) that a per-track rate is almost
    # pure noise; the same shrinkage keeps every circuit near the global rate
    # unless a track has genuinely earned its own.
    gr = red_flag_summary(status)
    global_rprob = gr["n_periods"] / gr["total_race_laps"] if gr["total_race_laps"] else 0.0

    out: dict[str, SafetyCarModel] = {}
    for event, g in status.groupby("event_name"):
        s = safety_car_summary(g)
        laps = s["total_race_laps"]
        prob = (s["n_periods"] + shrinkage_laps * global_prob) / (laps + shrinkage_laps)
        dur = s["mean_duration"] if s["n_periods"] > 0 else global_dur
        v = vsc_summary(g)
        vprob = (v["n_periods"] + shrinkage_laps * global_vprob) / (laps + shrinkage_laps)
        vdur = v["mean_duration"] if v["n_periods"] > 0 else global_vdur
        r = red_flag_summary(g)
        rprob = (r["n_periods"] + shrinkage_laps * global_rprob) / (laps + shrinkage_laps)
        out[str(event)] = SafetyCarModel(
            prob_per_lap=float(prob), mean_duration=int(round(dur)),
            vsc_prob_per_lap=float(vprob), vsc_mean_duration=max(1, int(round(vdur))),
            red_prob_per_lap=float(rprob),
        )
    return out


def track_sc_model(status: pd.DataFrame, event_name: str) -> SafetyCarModel:
    """Calibrated SC model for one circuit, falling back to the global rate.

    Convenience for the simulator/optimiser: returns the (shrunk) per-track model
    if the circuit is present in ``status``, else the global calibration.
    """
    per_track = calibrate_per_track(status)
    return per_track.get(event_name) or SafetyCarModel.from_track_status(status)


def sc_laps_in_race(race_status: pd.DataFrame) -> list[int]:
    """Race laps run under safety car: those where most cars show the SC code."""
    by_lap = race_status.groupby("lap_number")["track_status"].apply(
        lambda s: s.astype("string").str.contains(SC_CODE, na=False).mean()
    )
    return sorted(int(lap) for lap, frac in by_lap.items() if frac > 0.5)


def sc_period_durations(sc_laps: list[int]) -> list[int]:
    """Durations (in laps) of each contiguous safety-car period."""
    if not sc_laps:
        return []
    durations, start, prev = [], sc_laps[0], sc_laps[0]
    for lap in sc_laps[1:]:
        if lap == prev + 1:
            prev = lap
        else:
            durations.append(prev - start + 1)
            start = prev = lap
    durations.append(prev - start + 1)
    return durations


def vsc_laps_in_race(race_status: pd.DataFrame, *, exclude_sc: bool = True) -> list[int]:
    """Race laps run under a virtual safety car.

    ``exclude_sc`` drops laps that were already under a full SC, so the two
    hazards are calibrated from disjoint evidence and a race that escalated
    VSC → SC isn't counted twice.
    """
    by_lap = race_status.groupby("lap_number")["track_status"].apply(
        lambda s: s.astype("string").str.contains("|".join(VSC_CODES), na=False).mean()
    )
    laps = {int(lap) for lap, frac in by_lap.items() if frac > 0.5}
    if exclude_sc:
        laps -= set(sc_laps_in_race(race_status))
    return sorted(laps)


def red_flag_laps_in_race(race_status: pd.DataFrame) -> list[int]:
    """Race laps under a red flag (race suspended)."""
    by_lap = race_status.groupby("lap_number")["track_status"].apply(
        lambda s: s.astype("string").str.contains(RED_CODE, na=False).mean()
    )
    return sorted(int(lap) for lap, frac in by_lap.items() if frac > 0.5)


def red_flag_summary(status: pd.DataFrame) -> dict:
    """Same aggregate as :func:`safety_car_summary`, for red-flag laps."""
    n_periods = 0
    all_durations: list[int] = []
    total_race_laps = 0
    n_races = 0
    for _, race in status.groupby(["year", "round"]):
        n_races += 1
        total_race_laps += int(race["lap_number"].max())
        durations = sc_period_durations(red_flag_laps_in_race(race))
        n_periods += len(durations)
        all_durations.extend(durations)
    return {
        "n_races": n_races,
        "n_periods": n_periods,
        "periods_per_race": n_periods / n_races if n_races else 0.0,
        "mean_duration": float(np.mean(all_durations)) if all_durations else 0.0,
        "total_race_laps": total_race_laps,
    }


def vsc_summary(status: pd.DataFrame) -> dict:
    """Same aggregate as :func:`safety_car_summary`, for VSC-only laps."""
    n_periods = 0
    all_durations: list[int] = []
    total_race_laps = 0
    n_races = 0
    for _, race in status.groupby(["year", "round"]):
        n_races += 1
        total_race_laps += int(race["lap_number"].max())
        durations = sc_period_durations(vsc_laps_in_race(race))
        n_periods += len(durations)
        all_durations.extend(durations)
    return {
        "n_races": n_races,
        "n_periods": n_periods,
        "periods_per_race": n_periods / n_races if n_races else 0.0,
        "mean_duration": float(np.mean(all_durations)) if all_durations else 0.0,
        "total_race_laps": total_race_laps,
    }


def safety_car_summary(status: pd.DataFrame) -> dict:
    """Aggregate safety-car statistics across races from per-lap track status."""
    n_periods = 0
    all_durations: list[int] = []
    total_race_laps = 0
    races_with_sc = 0
    n_races = 0
    for _, race in status.groupby(["year", "round"]):
        n_races += 1
        total_race_laps += int(race["lap_number"].max())
        durations = sc_period_durations(sc_laps_in_race(race))
        if durations:
            races_with_sc += 1
        n_periods += len(durations)
        all_durations.extend(durations)
    return {
        "n_races": n_races,
        "n_periods": n_periods,
        "periods_per_race": n_periods / n_races if n_races else 0.0,
        "mean_duration": float(np.mean(all_durations)) if all_durations else 0.0,
        "total_race_laps": total_race_laps,
        "pct_races_with_sc": 100.0 * races_with_sc / n_races if n_races else 0.0,
    }
