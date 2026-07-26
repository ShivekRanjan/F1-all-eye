"""The combined lap dataset must never lose seasons it already had.

Regression test for a real incident: ``build_dry_dataset([2026])`` rebuilt
``dry_laps.parquet`` from the 2026 races alone, silently discarding ~61k
pre-2026 laps — the prior the era-shrinkage estimator is built on. Nothing
errored; the file just got smaller, and every degradation number computed
afterwards would have been quietly wrong.

No network: these exercise the combining logic against synthetic per-race
parquets, which is where the bug actually lived.
"""

from __future__ import annotations

import pandas as pd
import pytest

from f1se.data.ingest import combine_cached_races


def _race(year: int, rnd: int, n: int = 5) -> pd.DataFrame:
    return pd.DataFrame({
        "year": year, "round": rnd,
        "driver": [f"D{i}" for i in range(n)],
        "tyre_life": range(1, n + 1),
        "lap_time_fuel_corr_s": [90.0 + i for i in range(n)],
    })


def _write_cache(d, races):
    for year, rnd in races:
        _race(year, rnd).to_parquet(d / f"{year}_{rnd:02d}.parquet")


def test_combine_returns_every_cached_season(tmp_path):
    """The whole point: one season's ingest must not drop the others."""
    _write_cache(tmp_path, [(2024, 1), (2024, 2), (2025, 1), (2026, 1)])

    full = combine_cached_races(tmp_path)

    assert sorted(full["year"].unique().tolist()) == [2024, 2025, 2026]
    assert len(full) == 4 * 5
    # The pre-2026 prior is the thing that went missing in the incident.
    assert len(full[full["year"] < 2026]) == 15


def test_combine_picks_up_a_newly_added_race(tmp_path):
    """A freshly pulled race is written to the cache, so recombining sees it
    without re-reading anything else."""
    _write_cache(tmp_path, [(2026, 1), (2026, 2)])
    before = len(combine_cached_races(tmp_path))

    _write_cache(tmp_path, [(2026, 3)])
    after = combine_cached_races(tmp_path)

    assert len(after) == before + 5
    assert sorted(after["round"].unique().tolist()) == [1, 2, 3]


def test_combine_raises_on_an_empty_cache(tmp_path):
    """Better a loud failure than writing an empty dataset over a good one."""
    with pytest.raises(RuntimeError, match="no cached races"):
        combine_cached_races(tmp_path)
