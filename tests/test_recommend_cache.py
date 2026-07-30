"""The /recommend cache must isolate engines and evict, not flush.

Two defects found in review:

* the key used ``id(engine)`` — a memory address, which Python reuses once an
  object is collected (measured: 1998 reuses over 2000 short-lived objects).
  Nothing held a reference to the engine, so a fresh engine could land on a
  recycled address and silently read a previous engine's cached results. That
  is precisely what including the engine in the key was meant to prevent.
* overflow called ``.clear()``, wiping all 200 entries. One request past the
  limit forced the next 200 to recompute — seconds each on a small instance.
"""

from __future__ import annotations

import gc

from f1se import api


class _StubEngine:
    """Minimal stand-in: records calls so cache hits are observable."""

    def __init__(self, answer: str):
        self.answer = answer
        self.calls = 0

    def recommend(self, track, **kw):
        self.calls += 1
        return {"answer": self.answer, "track": track}


def _call(engine, track="A", **over):
    kw = dict(track=track, objective="mean", use_cliff=True, max_stops=2,
              n_runs=200, top_k=3, season=None, sc_scale=1.0, track_temp=None)
    kw.update(over)
    return api._recommend_cached(engine, **kw)


def _reset():
    api._REC_CACHE.clear()


def test_cache_returns_the_same_engines_result():
    _reset()
    e = _StubEngine("first")
    assert _call(e)["answer"] == "first"
    assert _call(e)["answer"] == "first"
    assert e.calls == 1, "second identical call should hit the cache"


def test_a_new_engine_never_inherits_a_dead_engines_entry():
    """The regression. Churn engines so an address is very likely recycled;
    every engine must still see only its own answer."""
    _reset()
    seen = []
    for i in range(60):
        e = _StubEngine(f"engine-{i}")
        seen.append(_call(e)["answer"])
        del e
        gc.collect()  # free the address for the next allocation
    assert seen == [f"engine-{i}" for i in range(60)], "an engine read a stale entry"


def test_two_live_engines_do_not_share_entries():
    _reset()
    a, b = _StubEngine("A"), _StubEngine("B")
    assert _call(a)["answer"] == "A"
    assert _call(b)["answer"] == "B"
    assert a.calls == 1 and b.calls == 1


def test_overflow_evicts_one_entry_not_the_whole_cache():
    _reset()
    e = _StubEngine("x")
    for i in range(api._REC_CACHE_MAX + 5):
        _call(e, track=f"T{i}")
    # A flush would leave a handful; correct LRU eviction stays at the cap.
    assert len(api._REC_CACHE) >= api._REC_CACHE_MAX - 1, (
        f"cache collapsed to {len(api._REC_CACHE)} — looks like a full clear()"
    )
    assert len(api._REC_CACHE) <= api._REC_CACHE_MAX


def test_eviction_is_least_recently_used():
    _reset()
    e = _StubEngine("x")
    _call(e, track="oldest")
    for i in range(api._REC_CACHE_MAX - 1):
        _call(e, track=f"T{i}")
    _call(e, track="oldest")          # refresh recency of the first entry
    _call(e, track="overflow")        # forces one eviction
    keys = [k[1] for k in api._REC_CACHE]
    assert "oldest" in keys, "recently-used entry was evicted"
    assert "T0" not in keys, "the genuinely-oldest entry should have gone"
