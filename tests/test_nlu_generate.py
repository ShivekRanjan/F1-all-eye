"""The generator's class balance — the bug that made the model look stupid.

`build()` used to draw an intent at random and discard any sentence it had
already produced. That reads as reasonable and is quietly fatal: `next_race`
takes no slots, so only a handful of distinct sentences exist for it, and once
they were used every further draw was thrown away — while `undercut`
(tracks x compounds x two ages x lap x phrasing) never ran out.

At n=60,000 that produced **6** next_race examples against 35,323 undercut, so
the model answered anything it didn't recognise with whichever class dominated.
Diagnosing that as model capacity would have been wrong twice over.
"""

from __future__ import annotations

from collections import Counter

from f1se.nlu.generate import ALL_INTENTS, build
from f1se.nlu.schema import Intent


def test_every_intent_gets_a_fair_share():
    pairs = build(2100, seed=0)
    c = Counter(g.intent for _, g in pairs)
    assert set(c) == set(ALL_INTENTS), "an intent was produced zero times"
    share = [v / len(pairs) for v in c.values()]
    # Exact quotas, so this is tight on purpose. The old behaviour put next_race
    # at 0.01% — any regression toward sampling-with-dedup blows through this.
    assert max(share) - min(share) < 0.01, dict(c)


def test_slot_free_intents_survive_at_training_scale():
    """The failure only showed at scale: at small n the sparse classes have not
    yet exhausted their distinct phrasings, so a small sample looks healthy."""
    c = Counter(g.intent for _, g in build(7000, seed=0))
    assert c[Intent.NEXT_RACE] > 900, f"next_race starved again: {c[Intent.NEXT_RACE]}"
    assert c[Intent.STANDINGS] > 900, f"standings starved again: {c[Intent.STANDINGS]}"


def test_there_is_a_reject_class_to_learn():
    """`unknown` is in the model's output space. With no examples it is a weight
    that never receives a gradient, so argmax over the real intents is the only
    thing the model can do — and every off-topic question becomes a confident
    wrong answer."""
    c = Counter(g.intent for _, g in build(2100, seed=0))
    assert c[Intent.UNKNOWN] > 100


def test_out_of_scope_examples_carry_no_slots():
    for text, gold in build(2100, seed=0):
        if gold.intent is Intent.UNKNOWN:
            assert gold.slots.filled() == {}, text


def test_generation_stays_linear():
    """Guards the latch in `build()`. Tolerating duplicates by re-testing a
    threshold on every draw cost 400 wasted samples per accepted duplicate,
    which turned a 20-second build into minutes and timed this suite out."""
    import time

    t0 = time.perf_counter()
    build(20000, seed=0)
    assert time.perf_counter() - t0 < 20
