"""Rule parser — the baseline the transformer has to beat.

Pins the two things that are easy to get quietly wrong: which circuit was meant,
and *whose* tyres are whose. A duel answered with the tyres on the wrong car is
worse than no answer, because it looks like an answer.
"""

from __future__ import annotations

import pytest

# Imported from the module under test, NOT from the `f1se.nlu` dispatcher.
# These assertions are about the rule parser specifically, and routing them
# through the dispatcher silently re-points the whole file at whatever happens
# to be the default parser — which is exactly what happened when the default
# moved to the hybrid and this file started failing for the wrong reason.
from f1se.nlu.lexicon import canonical_track
from f1se.nlu.rules import parse
from f1se.nlu.schema import Intent


# --- circuits ---------------------------------------------------------------
@pytest.mark.parametrize("text,expected", [
    ("mexico city gp", "Mexico City Grand Prix"),
    ("monza", "Italian Grand Prix"),
    ("imola", "Emilia Romagna Grand Prix"),
    ("spa", "Belgian Grand Prix"),
    ("interlagos", "São Paulo Grand Prix"),
    ("sao paulo", "São Paulo Grand Prix"),
    ("vegas", "Las Vegas Grand Prix"),
    ("cota", "United States Grand Prix"),
])
def test_circuit_aliases(text, expected):
    assert canonical_track(f"what is the strategy for {text}") == expected


def test_longest_alias_wins():
    """'mexico city' must beat 'mexico'; 'sao paulo' must not be read as 'spa'."""
    assert canonical_track("mexico city grand prix") == "Mexico City Grand Prix"
    assert canonical_track("sao paulo") == "São Paulo Grand Prix"


def test_alias_must_be_a_whole_word():
    """'spa' inside another word is not Belgium."""
    assert canonical_track("plenty of space on track") is None


# --- intents ----------------------------------------------------------------
@pytest.mark.parametrize("text,intent", [
    ("what's the fastest strategy for monaco", Intent.RECOMMEND),
    ("should i pit now to undercut him", Intent.UNDERCUT),
    ("how do the tyres degrade at silverstone", Intent.DEGRADATION),
    ("who is leading the championship", Intent.STANDINGS),
    ("who will win the next race", Intent.NEXT_RACE),
    ("who won at monza in 2025", Intent.RACE_RESULT),
])
def test_intents(text, intent):
    assert parse(text).intent is intent


def test_unparseable_says_so_rather_than_guessing():
    p = parse("what is the weather like tomorrow")
    assert p.intent is Intent.UNKNOWN
    assert p.confidence == 0.0


def test_undercut_beats_recommend_when_both_cues_appear():
    """An undercut question mentions strategy too; specificity must win."""
    assert parse("what's the best strategy — should i pit now to undercut him").intent is Intent.UNDERCUT


# --- tyre ownership, the part that actually matters -------------------------
def test_rival_tyres_are_not_assigned_to_you():
    """'X is behind me on softs' — the softs are X's. The phrase contains 'me',
    which is exactly the trap: a naive self-anchor binds them to the speaker
    and answers the duel backwards."""
    s = parse("verstappen is directly behind me on softs 2 laps old, lap 19 at abu dhabi").slots
    assert s.rival_compound == "SOFT"
    assert s.rival_age == 2
    assert s.your_compound is None, "the question never said what you are on"
    assert s.your_age is None


def test_explicit_self_and_rival_are_separated():
    s = parse("im on mediums 20 laps old, russell is 1.8s behind me on softs 3 laps old, lap 34 at monza").slots
    assert (s.your_compound, s.your_age) == ("MEDIUM", 20)
    assert (s.rival_compound, s.rival_age) == ("SOFT", 3)
    assert s.gap_s == 1.8
    assert s.rival_driver == "RUS"
    assert s.current_lap == 34


def test_lone_mention_with_no_anchors_belongs_to_the_speaker():
    s = parse("on mediums 18 laps old at spa lap 22, should i box").slots
    assert (s.your_compound, s.your_age) == ("MEDIUM", 18)
    assert s.rival_compound is None


def test_a_third_car_is_recorded_not_dropped():
    """The engine models a two-car duel. A third named car can't be folded in,
    so it must be surfaced rather than silently ignored."""
    s = parse("verstappen behind me on softs 2 laps old and hamilton on hards 15 laps old, lap 19").slots
    assert s.rival_driver == "VER"
    assert [r["driver"] for r in s.other_rivals] == ["HAM"]


# --- scalar slots -----------------------------------------------------------
def test_numbers_and_objectives():
    s = parse("whats the safest two stop strategy for imola in 2025").slots
    assert s.objective == "p85"
    assert s.max_stops == 2
    assert s.season == 2025
    assert s.track == "Emilia Romagna Grand Prix"


def test_compound_nicknames():
    s = parse("im on the reds 5 laps old, he is on whites, lap 10 at monza").slots
    assert s.your_compound == "SOFT"
    assert s.rival_compound == "HARD"


# --- contractions -----------------------------------------------------------
def test_apostrophes_do_not_split_the_ownership_anchors():
    """`normalise` used to turn "i'm" into "i m", which meant the parser's own
    `i'?m` / `he'?s` / `they'?re` anchors could never match anything it was
    given. With no self-anchor, neither tyre binds to a car and a fully
    specified duel comes back asking a question it was already told.

    The held-out set missed this entirely because it happens to be written
    without apostrophes, so this is the regression test that set can't be."""
    s = parse("i'm on softs 8 laps old at monza, he's on mediums 15 laps old, lap 22").slots
    assert (s.your_compound, s.your_age) == ("SOFT", 8)
    assert (s.rival_compound, s.rival_age) == ("MEDIUM", 15)


def test_curly_apostrophe_parses_like_the_straight_one():
    """Phones emit U+2019, not U+0027. Both must fold to the same token."""
    q = "i{a}m on hards 12 laps old at spa, he{a}s on softs 4 laps old, lap 20"
    straight = parse(q.format(a="'")).slots
    curly = parse(q.format(a="\u2019")).slots
    assert straight.your_compound == curly.your_compound == "HARD"
    assert straight.your_age == curly.your_age == 12
    assert straight.rival_compound == curly.rival_compound == "SOFT"


# --- definitional questions -------------------------------------------------
def test_a_definitional_question_is_refused_not_answered():
    """"What is an undercut?" asks about a word. The trigger words for an intent
    are the same words a definition is *about*, so without a guard the parser
    reads it as a request to run a duel and asks for a lap number the question
    was never going to supply."""
    for q in ("what is undercut?", "what is an undercut", "whats an undercut",
              "explain degradation", "what does deg mean"):
        assert parse(q).intent is Intent.UNKNOWN, q


def test_the_definitional_guard_never_eats_a_real_question():
    """Gated on "resolved no slots", so anything naming a circuit is untouched —
    and the two slot-free intents are exempt, because "what is the next race" is
    a genuine request for current state rather than a definition."""
    assert parse("what is the fastest strategy for Monza").intent is Intent.RECOMMEND
    assert parse("whats the deg like at Zandvoort").intent is Intent.DEGRADATION
    assert parse("what is the next race").intent is Intent.NEXT_RACE
    assert parse("what are the standings").intent is Intent.STANDINGS
