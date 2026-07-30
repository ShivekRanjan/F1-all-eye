"""Natural-language layer: turn a spoken/typed question into an engine call.

Two parsers live here and produce the same :class:`ParsedQuery`:

* :mod:`f1se.nlu.rules` — hand-written baseline
* :mod:`f1se.nlu.model` — a from-scratch transformer (see analysis/)

Which one ships is decided by measurement on a held-out set neither was tuned
on, not by preference. Same pattern as every other model choice in this repo.
"""

from f1se.nlu.schema import Intent, ParsedQuery, Slots

__all__ = ["Intent", "ParsedQuery", "Slots", "parse"]


def parse(text: str, *, parser: str = "rules") -> ParsedQuery:
    """Parse ``text``. ``parser`` selects the implementation."""
    if parser == "rules":
        from f1se.nlu.rules import parse as _p
        return _p(text)
    raise ValueError(f"unknown parser: {parser!r}")
