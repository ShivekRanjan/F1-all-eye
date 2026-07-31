"""`f1se.nlu.parse` must reach both implementations.

The transformer lost the head-to-head and does not ship as the default, but a
rejection nobody can re-run is just an assertion. These tests exist because the
transformer branch was once missing from the dispatcher entirely: the UI offered
a parser toggle and the API answered `unknown parser: 'transformer'`.
"""

import pytest

from f1se.config import PROJECT_ROOT
from f1se.nlu import Intent, parse

MODEL = PROJECT_ROOT / "data" / "processed" / "nlu_intent_slot.npz"
needs_model = pytest.mark.skipif(
    not MODEL.exists(), reason="trained NLU weights absent — run analysis/nlu_train.py")


def test_rules_is_the_default():
    assert parse("who leads the championship").parser == "rules"


def test_an_unknown_parser_name_is_an_error_not_a_silent_fallback():
    with pytest.raises(ValueError):
        parse("who leads the championship", parser="lstm")


@needs_model
def test_transformer_is_reachable_and_self_identifies():
    q = parse("who leads the championship", parser="transformer")
    assert q.parser == "transformer"
    assert q.intent is Intent.STANDINGS


@needs_model
def test_both_parsers_agree_on_a_fully_specified_duel():
    """Not a scored comparison — that lives in analysis/nlu_benchmark.py. This
    only pins that the two produce the same *type* of answer on an easy case,
    so a shape regression in either shows up here rather than in a benchmark
    nobody runs in CI."""
    q = "lap 30 at monza, im on hards 20 laps old, norris on mediums 6 laps old, do i box"
    a, b = parse(q, parser="rules"), parse(q, parser="transformer")
    assert a.intent is b.intent is Intent.UNDERCUT
    assert a.slots.track == b.slots.track == "Italian Grand Prix"
