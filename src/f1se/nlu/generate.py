"""Synthetic training data for the learned parser.

The labels are free: we know the slot values because we chose them, so a query
and its parse are generated together. That is the whole reason a from-scratch
model is viable here — no annotation budget, and as much data as we want.

The obvious trap is that a model trained on templates learns *the templates*.
Evaluating on more of the same would measure memorisation and report it as
skill. So the held-out set (`data/nlu/heldout.jsonl`) is hand-written, in
phrasings deliberately unlike anything below, and is never generated from here.

Surface variety is the point of the template list: the same question is asked
with different word order, contractions, fillers and abbreviations, so the model
has to learn *what a lap number looks like* rather than which slot follows the
fourth word.
"""

from __future__ import annotations

import random

from f1se.nlu.lexicon import (
    COMPOUND_ALIASES,
    DRIVER_ALIASES,
    TRACK_ALIASES,
)
from f1se.nlu.schema import Intent, ParsedQuery, Slots

# Aliases grouped by what they resolve to, so a sample can pick a canonical
# value first and then a way of saying it.
_TRACK_BY_CANON: dict[str, list[str]] = {}
for _a, _c in TRACK_ALIASES.items():
    _TRACK_BY_CANON.setdefault(_c, []).append(_a)

_COMPOUND_BY_CANON: dict[str, list[str]] = {}
for _a, _c in COMPOUND_ALIASES.items():
    _COMPOUND_BY_CANON.setdefault(_c, []).append(_a)

_DRIVER_BY_CODE: dict[str, list[str]] = {}
for _a, _c in DRIVER_ALIASES.items():
    _DRIVER_BY_CODE.setdefault(_c, []).append(_a)

GP_WORDS = ["gp", "grand prix", "", "race"]
LAP_PHRASES = ["lap {n}", "on lap {n}", "currently lap {n}", "we're on lap {n}",
               "it's lap {n}", "lap {n} of the race"]
AGE_PHRASES = ["{n} laps old", "{n} lap old", "{n} laps on them",
               "{n} laps used", "about {n} laps old", "roughly {n} laps old"]
SELF_PHRASES = ["i'm on", "im on", "i am on", "we're on", "my tyres are"]
RIVAL_LEAD = ["{d} is on", "{d} is behind me on", "{d} is right behind on",
              "{d}'s on", "he's on", "he is on", "they're on"]

RECOMMEND_T = [
    "what's the fastest strategy for {track}",
    "fastest strategy {track}",
    "best strategy for {track}",
    "what should i do at {track}",
    "how many stops at {track}",
    "optimal pit plan for {track}",
    "give me the strategy for {track}",
    "which tyres should i run at {track}",
    "what's the quickest way through {track}",
    "strategy for {track} please",
]
RECOMMEND_MOD = [
    "", " with {stops} stops", " {stops} stop", " the safe way", " conservatively",
    " in {season}", " risk averse",
]

UNDERCUT_T = [
    "{self} {yc} {ya}, {rival} {rc} {ra}, {lap}, should i pit",
    "{lap} at {track}. {self} {yc} {ya} and {rival} {rc} {ra}. undercut",
    "should i undercut? {self} {yc} {ya}, {rival} {rc} {ra}, {lap}",
    "{self} {yc} {ya}. {rival} {rc} {ra}. {lap} at {track}. pit now or cover",
    "at {track} {lap}, {self} {yc} {ya}, {rival} {rc} {ra}. undercut or hold",
    "{rival} {rc} {ra} and {self} {yc} {ya} at {track} {lap}. box now",
]
DEGRADATION_T = [
    "how do the tyres degrade at {track}",
    "tyre wear at {track}",
    "degradation at {track}",
    "how fast do tyres fall off at {track}",
    "what's the deg like at {track}",
]
STANDINGS_T = [
    "who's leading the championship", "championship standings",
    "who is winning the title", "current standings", "title race",
    "standings for {season}", "who leads the championship in {season}",
]
NEXT_RACE_T = [
    "what's the next race", "who will win the next race",
    "predicted podium for the next race", "when is the next grand prix",
    "next round prediction", "who's the favourite next race",
]
RESULT_T = [
    "who won at {track}", "what happened at {track}",
    "race result for {track}", "who won {track} in {season}",
    "finishing order at {track} {season}",
]


def _pick(rng: random.Random, seq):
    return seq[rng.randrange(len(seq))]


def _track(rng):
    canon = _pick(rng, sorted(_TRACK_BY_CANON))
    alias = _pick(rng, _TRACK_BY_CANON[canon])
    gp = _pick(rng, GP_WORDS)
    return (f"{alias} {gp}".strip(), canon)


def _compound(rng):
    canon = _pick(rng, sorted(_COMPOUND_BY_CANON))
    return _pick(rng, _COMPOUND_BY_CANON[canon]), canon


def _driver(rng):
    code = _pick(rng, sorted(_DRIVER_BY_CODE))
    return _pick(rng, _DRIVER_BY_CODE[code]), code


def sample(rng: random.Random) -> tuple[str, ParsedQuery]:
    """One (question, gold parse) pair."""
    intent = _pick(rng, [
        Intent.RECOMMEND, Intent.RECOMMEND, Intent.UNDERCUT, Intent.UNDERCUT,
        Intent.DEGRADATION, Intent.STANDINGS, Intent.NEXT_RACE, Intent.RACE_RESULT,
    ])
    s = Slots()

    if intent is Intent.RECOMMEND:
        tw, tc = _track(rng)
        s.track = tc
        text = _pick(rng, RECOMMEND_T).format(track=tw)
        mod = _pick(rng, RECOMMEND_MOD)
        if "{stops}" in mod:
            n = rng.choice([1, 2, 3])
            s.max_stops = n
            mod = mod.format(stops=_pick(rng, [str(n), ["one", "two", "three"][n - 1]]))
        elif "{season}" in mod:
            s.season = rng.choice([2023, 2024, 2025, 2026])
            mod = mod.format(season=s.season)
        elif "safe" in mod or "conservativ" in mod or "risk averse" in mod:
            s.objective = "p85"
        if "fastest" in text or "quickest" in text:
            s.objective = s.objective or "mean"
        text += mod

    elif intent is Intent.UNDERCUT:
        tw, tc = _track(rng)
        s.track = tc
        yc_w, yc = _compound(rng)
        rc_w, rc = _compound(rng)
        s.your_compound, s.rival_compound = yc, rc
        s.your_age = rng.randint(1, 35)
        s.rival_age = rng.randint(1, 35)
        s.current_lap = rng.randint(2, 60)
        dw, dcode = _driver(rng)
        rival_lead = _pick(rng, RIVAL_LEAD)
        if "{d}" in rival_lead:
            rival_lead = rival_lead.format(d=dw)
            s.rival_driver = dcode
        text = _pick(rng, UNDERCUT_T).format(
            self=_pick(rng, SELF_PHRASES), yc=yc_w,
            ya=_pick(rng, AGE_PHRASES).format(n=s.your_age),
            rival=rival_lead, rc=rc_w,
            ra=_pick(rng, AGE_PHRASES).format(n=s.rival_age),
            lap=_pick(rng, LAP_PHRASES).format(n=s.current_lap),
            track=tw,
        )

    elif intent is Intent.DEGRADATION:
        tw, tc = _track(rng)
        s.track = tc
        text = _pick(rng, DEGRADATION_T).format(track=tw)

    elif intent is Intent.STANDINGS:
        text = _pick(rng, STANDINGS_T)
        if "{season}" in text:
            s.season = rng.choice([2023, 2024, 2025, 2026])
            text = text.format(season=s.season)

    elif intent is Intent.NEXT_RACE:
        text = _pick(rng, NEXT_RACE_T)

    else:  # RACE_RESULT
        tw, tc = _track(rng)
        s.track = tc
        text = _pick(rng, RESULT_T)
        if "{season}" in text:
            s.season = rng.choice([2023, 2024, 2025])
            text = text.format(track=tw, season=s.season)
        else:
            text = text.format(track=tw)

    return text, ParsedQuery(intent=intent, slots=s, parser="gold")


def build(n: int, seed: int = 0) -> list[tuple[str, ParsedQuery]]:
    """``n`` unique (question, gold) pairs."""
    rng = random.Random(seed)
    seen: set[str] = set()
    out: list[tuple[str, ParsedQuery]] = []
    guard = 0
    while len(out) < n and guard < n * 40:
        guard += 1
        text, gold = sample(rng)
        if text in seen:
            continue
        seen.add(text)
        out.append((text, gold))
    return out
