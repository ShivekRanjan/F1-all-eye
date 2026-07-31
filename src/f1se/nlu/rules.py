"""Rule-based parser — the baseline.

Deliberately built first and built well. A challenger is only interesting if the
thing it beats is a fair fight, and the fastest way to make a learned model look
good is to benchmark it against a strawman. So this is the strongest hand-written
parser I can reasonably write: alias matching, positional reasoning about who
"you" and "the rival" are, and unit-aware number extraction.

It will be beaten on phrasings it wasn't written for. That is the point of the
experiment, not a defect to hide.
"""

from __future__ import annotations

import re

from f1se.nlu.lexicon import (
    COMPOUND_ALIASES,
    DRIVER_ALIASES,
    OBJECTIVE_ALIASES,
    canonical_track,
    normalise,
)
from f1se.nlu.schema import Intent, ParsedQuery, Slots

# --- intent cues ------------------------------------------------------------
# Ordered: the first pattern that fires wins, so the most specific go first.
# An undercut question mentions a strategy too, and would otherwise be
# swallowed by RECOMMEND.
INTENT_PATTERNS: list[tuple[Intent, list[str]]] = [
    (Intent.UNDERCUT, [
        r"\bunder ?cut\b", r"\bover ?cut\b", r"\bpit now\b", r"\bjump (him|her|them|the)\b",
        r"\bcover (him|her|them)\b", r"\bbehind me\b", r"\bahead of me\b",
        r"\bshould i (pit|stop|box)\b", r"\bbox now\b",
    ]),
    (Intent.DEGRADATION, [
        r"\bdeg(radation|s)?\b", r"\btyre wear\b", r"\btire wear\b",
        r"\bfall off\b", r"\bhow (do|does) the tyres?\b", r"\bcliff\b",
    ]),
    (Intent.STANDINGS, [
        r"\bstandings?\b", r"\bchampionship\b", r"\bwho('s| is) (leading|winning|top)\b",
        r"\btitle (race|odds|fight)\b", r"\bpoints table\b", r"\bleaderboard\b",
    ]),
    (Intent.NEXT_RACE, [
        r"\bnext (race|grand prix|gp|round)\b", r"\bwho will win\b",
        r"\bpredicted podium\b", r"\bwhen is the (next|upcoming)\b", r"\bupcoming\b",
    ]),
    (Intent.RACE_RESULT, [
        r"\bwhat happened\b", r"\bwho won\b", r"\brace result\b", r"\bresults? (at|for|of)\b",
        r"\bfinishing order\b",
    ]),
    (Intent.RECOMMEND, [
        r"\bstrateg(y|ies)\b", r"\bfastest\b", r"\bbest (plan|strategy|approach)\b",
        r"\bhow many stops?\b", r"\bone.?stop\b", r"\btwo.?stop\b", r"\bpit plan\b",
        r"\bwhat should (i|we) do\b", r"\bwhich tyres?\b",
    ]),
]

# "15 laps old", "2 lap old tyres", "on a 20 lap old set"
_AGE = r"(\d{1,2})\s*(?:laps?)\s*(?:old|used|on them)"
# "lap 19", "on lap 19", "currently lap 19", "we're on lap 19"
_LAP = r"(?:currently\s+|we(?:'re| are)\s+on\s+|on\s+)?lap\s*(\d{1,2})"
# "2 seconds behind", "1.5s back", "a gap of 2.4 seconds"
_GAP = r"(\d+(?:\.\d+)?)\s*(?:s\b|secs?\b|seconds?\b)"


def _first(pattern: str, text: str, group: int = 1) -> str | None:
    m = re.search(pattern, text)
    return m.group(group) if m else None


def detect_intent(text: str) -> tuple[Intent, float]:
    """First matching family wins; confidence reflects how many cues fired."""
    t = normalise(text)
    for intent, pats in INTENT_PATTERNS:
        hits = sum(1 for p in pats if re.search(p, t))
        if hits:
            return intent, min(1.0, 0.6 + 0.2 * hits)
    # No explicit cue, but the sentence may still *describe* a duel: two cars on
    # named tyres at a known lap is a strategy question whether or not the user
    # remembered to end it with one. People type the state and expect an answer
    # ("im on reds 5 laps old, he is on whites, lap 10 at monza"). Inferred, so
    # it carries lower confidence than a stated intent.
    n_comp = sum(1 for a in COMPOUND_ALIASES if re.search(rf"\b{a}\b", t))
    has_other = bool(re.search(r"\b(he|she|they|him|her|them|rival)\b", t)) or any(
        re.search(rf"\b{d}\b", t) for d in DRIVER_ALIASES)
    if n_comp >= 2 or (n_comp >= 1 and has_other and re.search(r"\blap\s*\d", t)):
        return Intent.UNDERCUT, 0.5
    return Intent.UNKNOWN, 0.0


def _compounds_in_order(text: str) -> list[tuple[int, str]]:
    """Every compound mention with its position, so 'you' vs 'rival' can be
    resolved by where each sits relative to the pronouns."""
    out: list[tuple[int, str]] = []
    for alias, canon in COMPOUND_ALIASES.items():
        for m in re.finditer(rf"\b{alias}\b", text):
            out.append((m.start(), canon))
    return sorted(out)


def _drivers_in_order(text: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for alias, code in DRIVER_ALIASES.items():
        for m in re.finditer(rf"\b{alias}\b", text):
            out.append((m.start(), code))
    # De-duplicate by code, keeping the earliest mention ("max verstappen").
    seen, uniq = set(), []
    for pos, code in sorted(out):
        if code not in seen:
            seen.add(code)
            uniq.append((pos, code))
    return uniq


#: "What is an undercut?" asks for a definition, not a duel. The words that
#: trigger an intent are the same words the definition is *about*, so without
#: this the parser reads "undercut" as a request to run one and then asks for a
#: lap number the question was never going to supply.
_DEFINITIONAL = re.compile(
    r"^(what (is|are|does|do)\b|whats (a|an|the)\b|explain\b|define\b"
    r"|how (does|do) .* work\b|what .*\bmean\b)")

#: Only intents that need a circuit are ambiguous this way. "What is the next
#: race" and "what is the championship standings" are genuine requests for
#: current state, not requests for a definition — so the two slot-free intents
#: are exempt, or the guard starts eating real questions.
_DEFINABLE = {Intent.RECOMMEND, Intent.UNDERCUT, Intent.DEGRADATION, Intent.RACE_RESULT}


def parse(text: str) -> ParsedQuery:
    """Sentence -> intent + slots. Never raises; UNKNOWN is a valid answer."""
    t = normalise(text)
    intent, conf = detect_intent(t)
    s = Slots()

    s.track = canonical_track(text)
    if (yr := _first(r"\b(20\d{2})\b", t)):
        s.season = int(yr)
    if (lap := _first(_LAP, t)):
        s.current_lap = int(lap)
    for word, obj in OBJECTIVE_ALIASES.items():
        if re.search(rf"\b{re.escape(word)}\b", t):
            s.objective = obj
            break
    if (st := _first(r"\b(one|two|three|1|2|3)[\s-]?stop", t)):
        s.max_stops = {"one": 1, "two": 2, "three": 3}.get(st, None) or int(st)

    if intent is Intent.UNDERCUT:
        _fill_duel(t, s)
    else:
        drivers = _drivers_in_order(t)
        if drivers:
            s.driver = drivers[0][1]

    # A definitional question that named nothing concrete is a question about a
    # word, not a request to run the engine. Gated on "no domain slot found" so
    # it can never swallow a real query: "what is the fastest strategy for
    # Monza" resolves a track and is left alone, while "what is an undercut"
    # resolves nothing and is correctly refused.
    if intent in _DEFINABLE and _DEFINITIONAL.match(t) and not s.filled():
        return ParsedQuery(intent=Intent.UNKNOWN, slots=Slots(), confidence=0.0,
                           parser="rules")

    return ParsedQuery(intent=intent, slots=s, confidence=conf, parser="rules")


def _fill_duel(t: str, s: Slots) -> None:
    """Work out which tyre belongs to whom.

    The hard part isn't finding "softs, 2 laps old" — it's deciding whose they
    are. People anchor with pronouns ("I'm on", "he's on") or with a name
    ("verstappen is on"), and the compound that follows the anchor is theirs.
    """
    ages = [(m.start(), int(m.group(1))) for m in re.finditer(_AGE, t)]
    comps = _compounds_in_order(t)
    drivers = _drivers_in_order(t)

    if (gap := _first(_GAP, t)):
        s.gap_s = float(gap)
    if (pit := _first(r"(?:pit|stop|box)(?:ting|s)?\s*(?:on\s*)?lap\s*(\d{1,2})", t)):
        s.rival_pit_lap = int(pit)

    # Anchors: where "you" are talked about, and where a rival is.
    #
    # "behind me" and "ahead of me" are RIVAL anchors that happen to contain the
    # word "me". Without the lookbehind, "verstappen is behind me on softs"
    # binds the softs to the speaker instead of to Verstappen — the tyres end up
    # on the wrong car and the duel is answered backwards. This is the kind of
    # error a hand-written parser makes and a learned one does not, which is
    # exactly what the benchmark is for.
    self_at = [m.start() for m in re.finditer(
        r"\b(i'?m|i am|my|we'?re|our|(?<!behind )(?<!ahead of )me)\b", t)]
    rival_at = [m.start() for m in re.finditer(
        r"\b(he'?s|he is|she'?s|she is|they'?re|they are|his|her|their|rival"
        r"|behind me|ahead of me)\b", t)]
    rival_at += [pos for pos, _ in drivers]

    def owner(pos: int) -> str | None:
        """Whose is the thing mentioned at ``pos``?

        Bind to the closest anchor *before* it — speech puts the owner first
        ("verstappen is on softs", "I'm on mediums"). Returning None when there
        is no preceding anchor is deliberate: an unowned mention means the
        question never said, and guessing would answer a duel with the tyres on
        the wrong car. Better to leave the slot empty and let the caller ask.
        """
        best, best_d = None, 10**9
        for a in self_at:
            if 0 <= pos - a < best_d:
                best, best_d = "you", pos - a
        for a in rival_at:
            if 0 <= pos - a < best_d:
                best, best_d = "rival", pos - a
        return best

    # With no anchors at all ("on mediums, 20 laps old, what now?") the speaker
    # is the only person in the sentence, so the lone mention is theirs.
    no_anchors = not self_at and not rival_at

    for pos, comp in comps:
        who = owner(pos) or ("you" if no_anchors else None)
        if who == "you" and s.your_compound is None:
            s.your_compound = comp
        elif who == "rival" and s.rival_compound is None:
            s.rival_compound = comp
    for pos, age in ages:
        who = owner(pos) or ("you" if no_anchors else None)
        if who == "you" and s.your_age is None:
            s.your_age = age
        elif who == "rival" and s.rival_age is None:
            s.rival_age = age
    if drivers:
        s.rival_driver = drivers[0][1]
        # A third car named makes this beyond a two-car duel. Record it so the
        # answer can say so instead of quietly dropping one.
        for _, code in drivers[1:]:
            s.other_rivals.append({"driver": code})
