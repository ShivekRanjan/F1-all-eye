"""Pre-register the engine's call for the next race, before it runs.

The Race Hub's "predicted vs actual" is already an honest forward test — the
podium model trains only on seasons before the one being predicted, so it never
sees the race it's scored on. But those predictions are *computed on demand*,
after the fact. A reader has to take our word that nothing was adjusted until
the predictions looked good.

This writes the call to disk *before* lights out, so the commit timestamp is the
evidence. Same idea as pre-registering a study before collecting the data: it
converts "trust us" into "check the git history".

Run it after qualifying (so the grid is real) and before the race:

    python analysis/preregister.py

Writes ``predictions/<season>_r<round>_<slug>.json`` and prints the call.
Scoring happens later, from the committed result — this file is never rewritten.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from f1se.config import PROJECT_ROOT
from f1se.standalone.outcome import _upcoming_context, predict_upcoming
from f1se.standalone.schedule import cached_calendar


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def main() -> int:
    payload = predict_upcoming()
    if payload is None:
        print("no results dataset — nothing to predict")
        return 1

    season, rnd = payload["season"], payload["next_round"]
    ctx = _upcoming_context()

    # Event name + race start come from the schedule, not the results dataset —
    # the round hasn't run, so it isn't in results yet.
    event, race_start = f"Round {rnd}", None
    cal = cached_calendar(season)
    if cal:
        for r in cal["rounds"]:
            if r["round"] == rnd:
                event = r["event_name"]
                if r["sessions"]:
                    race_start = r["sessions"][-1]["date"]
                break

    record = {
        "season": season,
        "round": rnd,
        "event_name": event,
        "made_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "race_start": race_start,
        "grid_source": payload["grid_source"],
        # Provenance: the model that made this call trained strictly before the
        # season it is predicting, which is what makes it a forward test.
        "model": {
            "trained_on_years": f"< {season}",
            "features": list(ctx["feature_cols"]) if ctx else [],
        },
        "called_podium": [p["driver"] for p in payload["predictions"][:3]],
        "predictions": [
            {"driver": p["driver"], "team": p["team"], "grid": p["grid"],
             "podium_prob": round(p["podium_prob"], 4)}
            for p in payload["predictions"]
        ],
        "scored": False,
    }

    out_dir = Path(PROJECT_ROOT) / "predictions"
    out_dir.mkdir(exist_ok=True)
    fp = out_dir / f"{season}_r{rnd}_{_slug(event)}.json"
    if fp.exists():
        print(f"{fp.name} already exists — refusing to overwrite a locked call")
        return 1
    fp.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {fp.relative_to(PROJECT_ROOT)}")
    print(f"  {event} (round {rnd}) · grid from {record['grid_source']}")
    print(f"  race starts {race_start}")
    for p in record["predictions"][:5]:
        print(f"    P{p['grid']:<2} {p['driver']:<4} {p['podium_prob']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
