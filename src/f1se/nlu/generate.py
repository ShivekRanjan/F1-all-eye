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

One rule when adding templates: **do not paraphrase the held-out set.** Writing a
training template that echoes a held-out phrasing leaks the test into the train
set just as surely as copying it, and it is easy to do by accident once you have
read that file. Four templates were removed for exactly this after the sparse
classes were expanded — "what's coming up next", "predicted top three next
race", "who's top of the championship", "points after the last round" — each a
near-paraphrase of a line in `heldout.jsonl`. If a new template feels natural
*because you remember reading it*, that is the tell.
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
    "how hard is the track on tyres at {track}",
    "tyre life at {track}",
    "how much do the tyres drop off at {track}",
    "what's tyre wear like round {track}",
    "how quickly do tyres go off at {track}",
]

#: Questions the engine genuinely cannot answer: definitions, regulations,
#: chit-chat, anything outside the six capabilities. Present so the model has a
#: reject class to predict — without them `unknown` is a label it has a weight
#: for and has never once been shown, so argmax over six real intents is the
#: only thing it can do and every off-topic question becomes a confident
#: wrong answer.
UNKNOWN_T = [
    "what is an undercut", "what is undercut", "explain the undercut",
    "what does undercut mean", "what is tyre degradation",
    "explain degradation", "what does deg mean", "what is a pit stop",
    "what does DRS mean", "what is DRS", "explain DRS",
    "what is a safety car", "what does VSC mean", "what is a virtual safety car",
    "what is parc ferme", "what does a red flag mean", "explain the points system",
    "how does qualifying work", "how do tyres work", "what are the tyre compounds",
    "what is a formation lap", "what does blue flag mean",
    "how does this app work", "what is this app", "what can you do",
    "who built this", "how does the model work", "what data do you use",
    "hello", "hi", "hey there", "thanks", "thank you", "good morning",
    "what's the weather like", "what time is it", "tell me a joke",
    "who is the best driver ever", "what's your favourite team",
    "how much does an f1 car cost", "how fast do f1 cars go",
    "what engine does ferrari use", "when did f1 start",
    "who has the most world titles", "how many races in a season",
]

#: Applied to every intent, never to one in particular — a filler that only ever
#: appeared on the sparse classes would be learned as a cue for those classes,
#: which trades a data bug for a subtler one.
PREFIX_FILLERS = ["", "", "", "", "hey ", "ok ", "quick one - ", "so ", "right, ",
                  "can you tell me ", "just wondering, "]
SUFFIX_FILLERS = ["", "", "", "", "?", " please", " mate", " thanks", " pls"]
STANDINGS_T = [
    "who's leading the championship", "championship standings",
    "who is winning the title", "current standings", "title race",
    "standings for {season}", "who leads the championship in {season}",
    "where are we in the title race", "drivers championship",
    "how do the standings look", "who's ahead in the championship",
    "points table", "who's winning the drivers title", "championship picture",
    "how many points is the leader on", "title standings in {season}",
    "championship table for {season}", "where does the championship stand",
]
NEXT_RACE_T = [
    "what's the next race", "who will win the next race",
    "predicted podium for the next race", "when is the next grand prix",
    "next round prediction", "who's the favourite next race",
    "who wins the next one", "podium call for the next round",
    "what race is next", "next grand prix prediction",
    "who takes the next win", "what's the next round",
    "give me the next race prediction", "who's tipped for the next race",
    "which race is up next", "who do you fancy next time out",
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


def _decorate(rng: random.Random, text: str) -> str:
    """Wrap a generated sentence in the fillers real questions arrive with."""
    return f"{_pick(rng, PREFIX_FILLERS)}{text}{_pick(rng, SUFFIX_FILLERS)}"


def sample(rng: random.Random, intent: Intent | None = None) -> tuple[str, ParsedQuery]:
    """One (question, gold parse) pair, optionally for a given intent."""
    if intent is None:
        intent = _pick(rng, [
            Intent.RECOMMEND, Intent.RECOMMEND, Intent.UNDERCUT, Intent.UNDERCUT,
            Intent.DEGRADATION, Intent.STANDINGS, Intent.NEXT_RACE, Intent.RACE_RESULT,
        ])
    s = Slots()

    if intent is Intent.UNKNOWN:
        return _decorate(rng, _pick(rng, UNKNOWN_T)), ParsedQuery(
            intent=intent, slots=s, parser="gold")

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

    return _decorate(rng, text), ParsedQuery(intent=intent, slots=s, parser="gold")


#: Every intent the model has an output weight for.
ALL_INTENTS = [Intent.RECOMMEND, Intent.UNDERCUT, Intent.DEGRADATION,
               Intent.STANDINGS, Intent.NEXT_RACE, Intent.RACE_RESULT, Intent.UNKNOWN]


def build(n: int, seed: int = 0) -> list[tuple[str, ParsedQuery]]:
    """``n`` (question, gold) pairs, balanced across intents.

    Balance is enforced per intent rather than left to sampling, because the two
    are not the same thing once duplicates are dropped. The old version drew an
    intent at random and discarded any sentence it had already emitted, which
    reads as reasonable and is quietly fatal: `next_race` has no slots, so there
    are only so many distinct ways to write it, and once they were used up every
    further draw was thrown away while `undercut` — tracks x compounds x two
    ages x lap x phrasing — never ran out.

    At n=60,000 that produced **6** next_race examples and **13** standings
    against 35,323 undercut. The model was not undertrained on those classes; it
    had effectively never seen them, which is why it answered anything it didn't
    recognise with whichever class dominated. Diagnosing that as model capacity
    would have been wrong twice over.

    So: fixed quota per intent, and once an intent exhausts its distinct
    phrasings it is allowed to repeat them. Repetition is honest — there really
    are only so many ways to ask who is leading the championship — whereas
    starvation silently rewrites the class priors.
    """
    rng = random.Random(seed)
    seen: set[str] = set()
    out: list[tuple[str, ParsedQuery]] = []
    quota, extra = divmod(n, len(ALL_INTENTS))

    for i, intent in enumerate(ALL_INTENTS):
        target = quota + (1 if i < extra else 0)
        made = misses = 0
        # Latched, not per-sample: once an intent has demonstrably run out of
        # distinct phrasings, stop deduping it altogether. Re-testing the
        # threshold on every draw made generation quadratic — 400 wasted
        # samples for each of thousands of accepted duplicates — which turned a
        # 20-second build into minutes.
        exhausted = False
        while made < target:
            text, gold = sample(rng, intent)
            if not exhausted and text in seen:
                misses += 1
                # Generous, so combinatorial intents never trip it and stay
                # fully unique.
                if misses < 400:
                    continue
                exhausted = True
            seen.add(text)
            out.append((text, gold))
            made += 1
    rng.shuffle(out)
    return out
