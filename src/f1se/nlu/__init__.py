"""Natural-language layer: turn a spoken/typed question into an engine call.

Two parsers live here and produce the same :class:`ParsedQuery`:

* :mod:`f1se.nlu.rules` — hand-written baseline
* :mod:`f1se.nlu.model` — a from-scratch transformer (see analysis/)

Which one ships is decided by measurement on a held-out set neither was tuned
on, not by preference. Same pattern as every other model choice in this repo.
"""

from functools import lru_cache

from f1se.nlu.schema import Intent, ParsedQuery, Slots

__all__ = ["Intent", "ParsedQuery", "Slots", "parse"]

#: Where the trained transformer weights live. Tracked in git (1.7 MB) and read
#: back through a numpy forward pass, so serving it costs no torch dependency.
_MODEL_REL = ("data", "processed", "nlu_intent_slot.npz")


@lru_cache(maxsize=1)
def _transformer():
    """Load the trained weights once per process.

    Cached because the alternative is re-reading and re-unpacking a 1.7 MB
    archive on every question, which would make the losing parser look slow for
    a reason that has nothing to do with the model.
    """
    from f1se.config import PROJECT_ROOT
    from f1se.nlu.model import NumpyIntentSlot

    path = PROJECT_ROOT.joinpath(*_MODEL_REL)
    if not path.exists():
        raise FileNotFoundError(
            f"no trained NLU model at {path} — run analysis/nlu_train.py")
    return NumpyIntentSlot.load(path)


def parse(text: str, *, parser: str = "rules") -> ParsedQuery:
    """Parse ``text``. ``parser`` selects the implementation.

    Both are reachable at runtime even though only the rules parser ships as the
    default. The transformer lost the head-to-head (METHODOLOGY §15) and keeping
    it callable is the difference between a documented rejection and an
    unverifiable claim — the comparison can be re-run from the app itself.
    """
    if parser == "rules":
        from f1se.nlu.rules import parse as _p
        return _p(text)
    if parser == "transformer":
        return _transformer().parse(text)
    raise ValueError(f"unknown parser: {parser!r}")
