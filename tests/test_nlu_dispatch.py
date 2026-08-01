"""`f1se.nlu.parse` must reach both implementations.

The transformer lost the head-to-head and does not ship as the default, but a
rejection nobody can re-run is just an assertion. These tests exist because the
transformer branch was once missing from the dispatcher entirely: the UI offered
a parser toggle and the API answered `unknown parser: 'transformer'`.
"""

import pytest

from f1se.config import PROJECT_ROOT
from f1se.nlu import Intent, parse, parse_followup

MODEL = PROJECT_ROOT / "data" / "processed" / "nlu_intent_slot.npz"
needs_model = pytest.mark.skipif(
    not MODEL.exists(), reason="trained NLU weights absent — run analysis/nlu_train.py")


def test_rules_is_reachable_and_self_identifies():
    assert parse("who leads the championship", parser="rules").parser == "rules"


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


@needs_model
def test_hybrid_is_the_default():
    assert parse("who leads the championship").parser == "hybrid"


@needs_model
def test_hybrid_takes_the_intent_from_the_model_and_the_slots_from_the_rules():
    """The composition is the point: each half is the one that won its half of
    the benchmark. "whats coming up next" is the case in miniature — the rule
    parser has no pattern for it and returns unknown, the transformer reads it
    correctly, and no rule was added to paper over it (that phrasing appears in
    the held-out set, so adding one would be fitting the test)."""
    assert parse("whats coming up next", parser="rules").intent is Intent.UNKNOWN
    assert parse("whats coming up next", parser="hybrid").intent is Intent.NEXT_RACE

    q = "lap 30 at monza, im on hards 20 laps old, norris on mediums 6 laps old, do i box"
    h = parse(q, parser="hybrid")
    r = parse(q, parser="rules")
    assert h.slots == r.slots, "slots must come from the rule parser verbatim"


@needs_model
def test_every_parser_refuses_a_definitional_question():
    for p in ("hybrid", "rules", "transformer"):
        assert parse("what is undercut?", parser=p).intent is Intent.UNKNOWN, p


# --- refinement follow-ups --------------------------------------------------
CTX = "fastest strategy for silverstone"


@needs_model
def test_a_refinement_resolves_against_the_previous_question():
    """"but the temperature is 35 degrees" means nothing alone. Parsed on its
    own the classifier reaches for whatever fits — it answered with the
    championship standings — so it has to be read against what came before."""
    p, merged = parse_followup("but the temprature is 35 degrees", CTX)
    assert merged
    assert p.intent is Intent.RECOMMEND
    assert p.slots.track == "British Grand Prix"
    assert p.slots.track_temp == 35.0


@needs_model
def test_a_refinement_overrides_the_slot_it_corrects():
    """Concatenation leaves the earlier wording in front, so "fastest ..." +
    "make it the safest" would keep reading as `mean` and silently discard the
    correction."""
    p, merged = parse_followup("make it the safest plan", CTX)
    assert merged and p.slots.objective == "p85"


@needs_model
def test_a_new_question_that_merely_follows_one_is_left_alone():
    """The gate is whether the fragment can stand on its own — judged on the
    rule parse, because the model is obliged to label every input and so makes
    every fragment look self-sufficient."""
    for q, want in (("who leads the championship", Intent.STANDINGS),
                    ("what happened at monza", Intent.RACE_RESULT),
                    ("how do the tyres go off at spa", Intent.DEGRADATION)):
        p, merged = parse_followup(q, CTX)
        assert not merged, q
        assert p.intent is want, q
    # ...and the circuit named in the follow-up must survive, not be replaced.
    assert parse_followup("what happened at monza", CTX)[0].slots.track == "Italian Grand Prix"


@needs_model
def test_no_context_means_no_merge():
    p, merged = parse_followup("but the temprature is 35 degrees", None)
    assert not merged and p.slots.track is None


# --- evaluation sets --------------------------------------------------------
def test_every_evaluation_set_parses_and_stays_disjoint():
    """Guards the thing that makes a second set worth having. If a phrasing
    appears in both, the fresh set inherits the spent one's history and stops
    being an independent estimate — the exact failure §15 is about."""
    import sys

    sys.path.insert(0, str(PROJECT_ROOT / "analysis"))
    from nlu_benchmark import load_sets

    sets = load_sets()
    assert sets, "no evaluation sets found"
    seen: dict[str, str] = {}
    for name, _desc, pairs in sets:
        assert pairs, f"{name} is present but empty"
        for text, gold in pairs:
            key = text.strip().lower()
            assert key not in seen, f"{text!r} appears in both {seen[key]} and {name}"
            seen[key] = name
            assert gold.intent is not None
