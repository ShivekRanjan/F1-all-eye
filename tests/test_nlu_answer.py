"""Answering layer: parsed question -> engine call -> spoken sentence.

Focuses on the behaviours that make a chatbot trustworthy rather than merely
functional: it asks when a slot is missing, it never contradicts itself, and it
surfaces the limits of the two-car duel instead of quietly answering a narrower
question than the one asked.
"""

from __future__ import annotations

from f1se.nlu import parse
from f1se.nlu.answer import answer


class _StubEngine:
    """Records calls so routing can be asserted without running Monte Carlo."""

    def __init__(self):
        self.calls = []

    def recommend(self, track, **kw):
        self.calls.append(("recommend", track, kw))
        return {"best": {"compounds": ["MEDIUM", "HARD"], "pit_laps": [23],
                         "mean_s": 5040.0, "p50_s": 5010.0, "p90_s": 5200.0},
                "shortlist": [{"win_prob_vs_best": 1.0}, {"win_prob_vs_best": 0.3}]}

    def undercut(self, track, **kw):
        self.calls.append(("undercut", track, kw))
        return {"undercut": {"final_gap_s": -0.4, "p_ahead": 0.7},
                "cover": {"final_gap_s": 1.6, "p_ahead": 0.1},
                "undercut_gain_s": 2.0, "undercut_works": True,
                "beyond_modelled_range": []}


def test_missing_slot_asks_instead_of_guessing():
    """The question never says what YOU are on. Defaulting there would answer a
    duel with the tyres on the wrong car."""
    a = answer(parse("verstappen is behind me on softs 2 laps old, lap 19 at monza"), _StubEngine())
    assert "your_compound" in a.needs
    assert a.followup and "tyre" in a.followup.lower()


def test_unknown_intent_is_admitted():
    a = answer(parse("what is the weather tomorrow"), _StubEngine())
    assert a.needs == ["intent"]
    assert "didn't catch" in a.text


def test_recommend_routes_and_phrases():
    eng = _StubEngine()
    a = answer(parse("fastest strategy for monza"), eng)
    assert eng.calls[0][0] == "recommend"
    assert eng.calls[0][1] == "Italian Grand Prix"
    assert "1-stop" in a.text and "medium then hard" in a.text


def test_undercut_never_says_pit_now_and_zero_percent():
    """Both statements can be true at once — the undercut is better AND doesn't
    get you past — but together they read as broken. When the pass isn't on,
    say so rather than quoting a probability that rounds to zero."""
    eng = _StubEngine()
    eng.undercut = lambda track, **kw: {
        "undercut": {"final_gap_s": 10.1, "p_ahead": 0.0005},
        "cover": {"final_gap_s": 12.5, "p_ahead": 0.0},
        "undercut_gain_s": 2.4, "undercut_works": True,
        "beyond_modelled_range": [],
    }
    a = answer(parse("im on mediums 20 laps old, russell is 1.8s behind me on softs 3 laps old, lap 34 at monza"), eng)
    assert "0% of the time" not in a.text
    assert "closes the gap" in a.text


def test_third_car_is_surfaced_not_dropped():
    eng = _StubEngine()
    q = ("im on hards 10 laps old, verstappen is behind me on softs 2 laps old "
         "and hamilton is on mediums 15 laps old, lap 19 at monza")
    a = answer(parse(q), eng)
    assert a.note and "two-car duel" in a.note
    assert "HAM" in a.note


def test_answer_always_reports_what_it_understood():
    a = answer(parse("fastest strategy for spa"), _StubEngine())
    assert a.parsed["slots"]["track"] == "Belgian Grand Prix"
    assert a.parsed["parser"] == "rules"


def test_a_negative_degradation_slope_is_not_read_out_as_a_double_negative():
    """Track evolution can outrun tyre wear, giving a genuinely negative slope.
    "loses about -0.027 seconds per lap" is true and unreadable."""
    from f1se.nlu.answer import _slope_phrase

    assert _slope_phrase("SOFT", -0.027) == "soft actually gains about 0.027 seconds per lap"
    assert _slope_phrase("HARD", 0.043) == "hard loses about 0.043 seconds per lap"


# --- "last race" ------------------------------------------------------------
def test_who_won_last_race_resolves_instead_of_asking_which_circuit(monkeypatch):
    """The ask-don't-assume rule is for slots nothing can supply. Which race was
    the last one is not one of them — the app holds the calendar. Bouncing this
    back with "Which circuit?" is consistent and useless."""
    import f1se.nlu.answer as A

    monkeypatch.setattr(A, "_last_completed_round", lambda: (2026, "Hungarian Grand Prix"))
    monkeypatch.setattr(
        "f1se.standalone.races.cached_race_card",
        lambda season, track: {"event_name": track, "actual_podium": ["NOR", "VER", "ANT"]},
    )

    a = answer(parse("who won last race?"), None)
    assert a.needs == []
    assert "Hungarian Grand Prix" in a.text
    # The inference has to be visible in both the sentence and the parse — an
    # assumption the user can't see is the failure this view exists to prevent.
    assert a.text.startswith("Last time out")
    assert a.parsed["slots"]["track"] == "Hungarian Grand Prix"


def test_a_named_circuit_is_never_overridden_by_the_last_race(monkeypatch):
    import f1se.nlu.answer as A

    monkeypatch.setattr(A, "_last_completed_round", lambda: (2026, "Hungarian Grand Prix"))
    monkeypatch.setattr(
        "f1se.standalone.races.cached_race_card",
        lambda season, track: {"event_name": track, "actual_podium": ["LEC", "RUS", "HAM"]},
    )

    a = answer(parse("what happened at Silverstone"), None)
    assert a.parsed["slots"]["track"] == "British Grand Prix"
    assert not a.text.startswith("Last time out")


def test_it_still_asks_when_the_calendar_cannot_say(monkeypatch):
    """No resolution available (pre-season, or the schedule fetch failed) must
    fall back to the question, not to a guess."""
    import f1se.nlu.answer as A

    monkeypatch.setattr(A, "_last_completed_round", lambda: None)
    a = answer(parse("who won last race?"), None)
    assert a.needs == ["track"]
    assert a.text == "Which circuit?"
