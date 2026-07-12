"""Driver metadata (code → full name, team, country) for the V2 UI.

The results dataset keeps only the 3-letter abbreviation; the V2 design shows
each driver's full name on hover (ANT → Kimi Antonelli) and a team-coloured
avatar. Names/nationality are stable within a season, so this pulls one
representative race per season from FastF1 and merges — a tiny committed
lookup, refreshed with ``python -m f1se.standalone.drivers_meta``.
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from f1se.config import PROJECT_ROOT, enable_cache
from f1se.standalone.outcome import _resolve_results

PROCESSED = PROJECT_ROOT / "data" / "processed"
OUT = PROCESSED / "driver_info.parquet"


def build_driver_info(seasons: list[int] | None = None) -> pd.DataFrame:
    """Pull code→name/team/country from the latest race of each season, merged."""
    enable_cache()
    import fastf1

    seasons = seasons or [2023, 2024, 2025, 2026]
    rows: list[pd.DataFrame] = []
    for yr in seasons:
        try:
            sched = fastf1.get_event_schedule(yr, include_testing=False)
            done = [int(r) for r in sched["RoundNumber"] if int(r) >= 1]
            for rnd in reversed(done):  # newest race first — usually the full grid
                try:
                    s = fastf1.get_session(yr, rnd, "R")
                    s.load(laps=False, telemetry=False, weather=False, messages=False)
                    r = s.results
                    rows.append(pd.DataFrame({
                        "driver": r["Abbreviation"].astype("string"),
                        "full_name": r["FullName"].astype("string"),
                        "team": r["TeamName"].astype("string"),
                        "country": r["CountryCode"].astype("string"),
                        "year": yr,
                    }))
                    break
                except Exception:  # pragma: no cover - network
                    continue
        except Exception:  # pragma: no cover - network
            continue

    if not rows:
        raise RuntimeError("no driver metadata pulled")
    df = pd.concat(rows, ignore_index=True)
    # Latest season wins for each driver (current team/name).
    df = (df.sort_values("year").dropna(subset=["driver"])
          .groupby("driver", observed=True).tail(1)
          .drop(columns="year").reset_index(drop=True))
    df.to_parquet(OUT)
    print(f"DONE: {len(df)} drivers -> {OUT}", flush=True)
    return df


@lru_cache(maxsize=1)
def driver_info() -> dict[str, dict]:
    """``{code: {name, team, country}}`` from the committed lookup ({} if absent)."""
    fp = OUT if OUT.exists() else (_resolve_results(None).parent / "driver_info.parquet"
                                   if _resolve_results(None) else None)
    if fp is None or not fp.exists():
        return {}
    df = pd.read_parquet(fp)
    return {
        str(r.driver): {
            "name": None if pd.isna(r.full_name) else str(r.full_name),
            "team": None if pd.isna(r.team) else str(r.team),
            "country": None if pd.isna(r.country) else str(r.country),
        }
        for r in df.itertuples(index=False)
    }


if __name__ == "__main__":
    build_driver_info()
