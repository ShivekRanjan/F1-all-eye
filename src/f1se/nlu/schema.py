"""What a parsed question looks like.

The whole NLU layer exists to turn a sentence into one of these, which the API
then maps onto an existing engine call. Nothing here models anything — it is a
translation layer, and keeping it that way is the same decoupling rule that
keeps ``api.py`` thin (see CLAUDE.md).

Both parsers — the rule baseline and the from-scratch transformer — produce this
identical type, which is what makes them comparable on the same held-out set.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum


class Intent(StrEnum):
    """What the user is asking for. Each maps to one engine capability."""

    RECOMMEND = "recommend"        # fastest strategy for a race
    UNDERCUT = "undercut"          # pit now to jump a rival?
    DEGRADATION = "degradation"    # how do the tyres fall off here
    STANDINGS = "standings"        # championship state
    NEXT_RACE = "next_race"        # what's next / who's predicted
    RACE_RESULT = "race_result"    # what happened at a past race
    UNKNOWN = "unknown"            # parsed nothing usable — say so, don't guess


@dataclass
class Slots:
    """Extracted parameters. Every field optional: a question rarely fills all."""

    track: str | None = None
    season: int | None = None
    current_lap: int | None = None
    objective: str | None = None          # mean | median | p85
    max_stops: int | None = None
    #: Expected track temperature, °C. Feeds the thermal prior — the correction
    #: that took the season backtest's stop-count match from 4/8 to 7/8
    #: (METHODOLOGY §9). The engine and the Strategy view have always taken it;
    #: the chat could not reach it until this slot existed.
    track_temp: float | None = None

    # Undercut duel — "you" versus one rival.
    gap_s: float | None = None
    your_compound: str | None = None
    your_age: int | None = None
    your_new_compound: str | None = None
    rival_compound: str | None = None
    rival_age: int | None = None
    rival_new_compound: str | None = None
    rival_pit_lap: int | None = None
    rival_driver: str | None = None

    # Extra rivals named in the question. The engine models a TWO-car duel, so a
    # three-car question can only be answered as separate duels — recorded here
    # so the answer can say that rather than silently dropping one.
    other_rivals: list[dict] = field(default_factory=list)

    driver: str | None = None

    def filled(self) -> dict:
        """Only the slots that were actually found — the rest are not 'None',
        they are 'not asked about', and defaults belong to the engine."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v not in (None, [], {})}


@dataclass
class ParsedQuery:
    """A parse, plus enough provenance to show the user what was understood."""

    intent: Intent
    slots: Slots
    confidence: float = 1.0
    #: Which parser produced this — "rules" or "transformer". Recorded so the
    #: benchmark can attribute every answer, and so the UI can say.
    parser: str = "rules"
    #: Slots the question implied but the engine has no place for.
    unsupported: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "intent": self.intent.value,
            "slots": self.slots.filled(),
            "confidence": round(self.confidence, 3),
            "parser": self.parser,
            "unsupported": self.unsupported,
        }
