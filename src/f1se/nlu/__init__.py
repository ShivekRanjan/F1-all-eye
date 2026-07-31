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


def _hybrid(text: str) -> ParsedQuery:
    """Transformer for the intent, rules for the slots.

    Not a hedge — each half is the one that measurably won its half. Across three
    seeds on the hand-written set the transformer takes intent 3/3 (0.645-0.677
    vs 0.516) while the rule parser takes slot extraction 3/3, at **precision
    1.000** against 0.974-0.978. Composing them keeps both: intent accuracy rises
    to the transformer's, slot precision stays perfect, and exact match goes
    0.290 -> 0.419-0.452.

    The split is not arbitrary either. Classifying a sentence into one of seven
    intents is pattern recognition over the whole utterance, which is what a
    learned model is for; pulling "18 laps old" out and deciding *whose* tyres
    they are is bounded, checkable logic with a right answer, which is what a
    rule is for. That the measurement agrees with that reasoning is the reason to
    trust it.

    Pre-registered: METHODOLOGY §15 named this experiment before the data that
    confirms it existed.
    """
    from f1se.nlu.rules import parse as _rules

    return compose(_transformer().parse(text), _rules(text))


def compose(t: ParsedQuery, r: ParsedQuery) -> ParsedQuery:
    """Combine a model parse and a rule parse into the shipped answer.

    Split out so `analysis/nlu_benchmark.py` scores the composition that
    actually ships rather than its own re-implementation of it — the two drifting
    apart is how a benchmark starts measuring something nobody runs.
    """
    from f1se.nlu.schema import Intent

    intent = t.intent
    # The slots are evidence about the intent, not just cargo. A sentence that
    # names two cars on different tyres at a given lap IS a duel, whatever a
    # classifier scores it — and the model does get this wrong: "verstappen is
    # behind me on softs 2 laps old, lap 19 at monza" came back as `degradation`
    # at 0.594 while the rule parser read it correctly.
    #
    # Deliberately a structural check and not a confidence threshold. Thresholds
    # have to be tuned, and the only set available to tune one against is the 31
    # examples that decide the benchmark.
    s = r.slots
    duel = (s.your_compound and s.rival_compound) or (
        s.rival_compound and s.rival_age is not None and s.current_lap is not None)
    if duel:
        intent = Intent.UNDERCUT

    return ParsedQuery(intent=intent, slots=s, confidence=t.confidence,
                       parser="hybrid", unsupported=r.unsupported)


def parse(text: str, *, parser: str = "hybrid") -> ParsedQuery:
    """Parse ``text``. ``parser`` selects the implementation.

    All three are reachable at runtime, because a benchmark nobody can re-run is
    an assertion rather than a result — the comparison in METHODOLOGY §15 can be
    reproduced from the app itself.
    """
    if parser == "hybrid":
        return _hybrid(text)
    if parser == "rules":
        from f1se.nlu.rules import parse as _p
        return _p(text)
    if parser == "transformer":
        return _transformer().parse(text)
    raise ValueError(f"unknown parser: {parser!r}")
