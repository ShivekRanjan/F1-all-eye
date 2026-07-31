"""Turn a parsed question into a spoken answer plus the data behind it.

Two rules shape everything here.

**Say what was understood.** Parsing is fuzzy, so every answer carries the
resolved parameters. A user who sees "Monza · lap 34 · you MEDIUM 20 laps" can
tell instantly that the bot heard "Monaco" when they said "Monza", which is the
difference between a wrong answer and a caught mistake.

**Ask rather than assume.** A missing slot is a question, not a default. The
engine has sensible defaults for plenty of things, but "what tyre are you on"
is not one of them — guessing there produces a confident answer to a question
nobody asked.

The text is written to be *spoken*: short sentences, no tables, numbers rounded
to what a person would say out loud. The structured payload carries the detail
for the screen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from f1se.nlu.schema import Intent, ParsedQuery

# What each intent cannot proceed without.
REQUIRED: dict[Intent, tuple[str, ...]] = {
    Intent.RECOMMEND: ("track",),
    Intent.UNDERCUT: ("track", "current_lap", "your_compound", "your_age",
                      "rival_compound", "rival_age"),
    Intent.DEGRADATION: ("track",),
    Intent.RACE_RESULT: ("track",),
    Intent.STANDINGS: (),
    Intent.NEXT_RACE: (),
}

ASK_FOR: dict[str, str] = {
    "track": "Which circuit?",
    "current_lap": "What lap are we on?",
    "your_compound": "What tyre are you on?",
    "your_age": "How old are your tyres?",
    "rival_compound": "What tyre is your rival on?",
    "rival_age": "How old are their tyres?",
}


@dataclass
class Answer:
    text: str
    parsed: dict
    data: dict | None = None
    needs: list[str] = field(default_factory=list)
    followup: str | None = None
    note: str | None = None

    def to_dict(self) -> dict:
        return {"text": self.text, "parsed": self.parsed, "data": self.data,
                "needs": self.needs, "followup": self.followup, "note": self.note}


def _clock(sec: float) -> str:
    """Race times the way a commentator says them."""
    m, s = divmod(int(round(sec)), 60)
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"


def _stint_phrase(compounds: list[str], pit_laps: list[int]) -> str:
    """'medium then hard, stopping on lap 23'."""
    tyres = " then ".join(c.lower() for c in compounds)
    if not pit_laps:
        return f"{tyres}, no stop"
    laps = " and ".join(str(p) for p in pit_laps)
    stop_word = "stopping on lap" if len(pit_laps) == 1 else "stopping on laps"
    return f"{tyres}, {stop_word} {laps}"


def answer(pq: ParsedQuery, engine) -> Answer:
    """Route a parsed question to the engine and phrase the result."""
    parsed = pq.to_dict()
    s = pq.slots

    if pq.intent is Intent.UNKNOWN:
        return Answer(
            text=("I didn't catch a strategy question there. Try something like "
                  "\"fastest strategy for Monza\", or tell me the lap and what "
                  "you and your rival are on."),
            parsed=parsed, needs=["intent"],
        )

    missing = [f for f in REQUIRED.get(pq.intent, ()) if getattr(s, f, None) is None]
    if missing:
        first = missing[0]
        return Answer(
            text=ASK_FOR.get(first, f"I still need {first.replace('_', ' ')}."),
            parsed=parsed, needs=missing, followup=ASK_FOR.get(first),
        )

    try:
        if pq.intent is Intent.RECOMMEND:
            return _recommend(s, engine, parsed)
        if pq.intent is Intent.UNDERCUT:
            return _undercut(s, engine, parsed)
        if pq.intent is Intent.DEGRADATION:
            return _degradation(s, engine, parsed)
        if pq.intent is Intent.STANDINGS:
            return _standings(s, parsed)
        if pq.intent is Intent.NEXT_RACE:
            return _next_race(parsed)
        if pq.intent is Intent.RACE_RESULT:
            return _race_result(s, parsed)
    except KeyError as e:
        return Answer(text=f"I don't have data for that: {e}", parsed=parsed)
    except Exception as e:  # pragma: no cover - engine/network surface
        return Answer(text=f"That query failed: {e}", parsed=parsed)

    return Answer(text="I couldn't work out what to do with that.", parsed=parsed)


def _recommend(s, engine, parsed) -> Answer:
    r = engine.recommend(
        s.track, objective=s.objective or "mean",
        max_stops=s.max_stops or 2, season=s.season, n_runs=1500, top_k=3,
    )
    best = r["best"]
    plan = _stint_phrase(list(best["compounds"]), list(best["pit_laps"]))
    n = len(best["pit_laps"])
    conf = r["shortlist"][1]["win_prob_vs_best"] if len(r["shortlist"]) > 1 else None
    text = (f"At {s.track}, the {'fastest' if (s.objective or 'mean') == 'mean' else 'recommended'} "
            f"plan is a {n}-stop: {plan}. Expected race time {_clock(best['mean_s'])}.")
    if conf is not None:
        margin = 100 * (1 - conf)
        text += (f" It's a clear call — it beats the next-best plan {margin:.0f}% of the time."
                 if margin >= 60 else
                 f" It's close, though: the next-best plan wins {100 * conf:.0f}% of the time.")
    return Answer(text=text, parsed=parsed, data=r)


def _undercut(s, engine, parsed) -> Answer:
    r = engine.undercut(
        s.track, current_lap=s.current_lap, gap_s=s.gap_s if s.gap_s is not None else 1.5,
        your_compound=s.your_compound, your_age=s.your_age,
        your_new_compound=s.your_new_compound or "HARD",
        rival_compound=s.rival_compound, rival_age=s.rival_age,
        rival_new_compound=s.rival_new_compound or "HARD",
        rival_pit_lap=s.rival_pit_lap or (s.current_lap + 5),
        season=s.season, n_runs=1500,
    )
    gain, works = r["undercut_gain_s"], r["undercut_works"]
    chosen = r["undercut"] if works else r["cover"]
    p, final_gap = chosen["p_ahead"], chosen["final_gap_s"]
    who = f"{s.rival_driver}" if s.rival_driver else "your rival"

    # "Pit now — you come out ahead 0% of the time" is the kind of sentence that
    # destroys trust in a tool. Both statements are true (the undercut IS the
    # better option, and it still doesn't get you past), but read together they
    # sound broken. When the pass isn't on, say that instead of quoting a
    # probability that rounds to zero.
    if works:
        head = f"Yes — pit now. The undercut gains about {abs(gain):.1f} seconds on {who}"
    else:
        head = f"No — hold and cover. Undercutting only gains {gain:+.1f} seconds"
    if p >= 0.10:
        text = f"{head}, and you come out ahead {p * 100:.0f}% of the time."
    elif final_gap > 0:
        text = (f"{head}, but it isn't enough to get past — you'd still be about "
                f"{final_gap:.0f} seconds behind at the crossover. It closes the gap, "
                f"it doesn't make the pass.")
    else:
        text = f"{head}, and you hold the position."

    note = None
    if s.other_rivals:
        others = ", ".join(o["driver"] for o in s.other_rivals)
        note = (f"You mentioned {others} as well. The engine models a two-car duel, "
                f"so this answer covers {who} only — ask again naming {others} "
                f"to run that duel separately.")
    if r.get("beyond_modelled_range"):
        b = r["beyond_modelled_range"][0]
        note = ((note + " ") if note else "") + (
            f"Careful: {b['compound'].lower()} at {b['age']} laps is past anything the "
            f"field has run here ({b['modelled_to']}), so the wear estimate flatters "
            f"whoever stays out.")
    return Answer(text=text, parsed=parsed, data=r, note=note)


def _slope_phrase(compound: str, slope: float) -> str:
    """A degradation slope, said out loud.

    Negative slopes are real, not glitches: on a green, evolving track the
    rubber goes down faster than the tyre wears out, so a stint gets *quicker*.
    But "loses about -0.027 seconds per lap" is a double negative the reader has
    to unpick, so say what it means instead of printing the sign.
    """
    if slope < 0:
        return f"{compound.lower()} actually gains about {abs(slope):.3f} seconds per lap"
    return f"{compound.lower()} loses about {slope:.3f} seconds per lap"


def _degradation(s, engine, parsed) -> Answer:
    d = engine.degradation_curves(s.track, season=s.season)
    comps = d.get("compounds", {})
    if not comps:
        return Answer(text=f"I have no tyre data for {s.track}.", parsed=parsed)
    parts = [_slope_phrase(c, v["slope"])
             for c, v in comps.items() if v.get("slope") is not None]
    return Answer(text=f"At {s.track}, " + "; ".join(parts) + ".", parsed=parsed, data=d)


def _standings(s, parsed) -> Answer:
    from f1se.standalone.standings import cached_standings

    st = cached_standings(s.season)
    if not st or not st.get("drivers"):
        return Answer(text="I don't have standings for that season.", parsed=parsed)
    d = st["drivers"]
    lead, second = d[0], (d[1] if len(d) > 1 else None)
    text = f"{lead['driver']} leads the {st['season']} championship on {lead['points']:.0f} points"
    if second:
        text += f", {lead['points'] - second['points']:.0f} clear of {second['driver']}"
    if lead.get("win_prob") is not None:
        text += f". Title odds put them at {lead['win_prob'] * 100:.0f}%"
    return Answer(text=text + ".", parsed=parsed, data=st)


def _next_race(parsed) -> Answer:
    from f1se.standalone.outcome import predict_upcoming
    from f1se.standalone.schedule import cached_calendar

    up = predict_upcoming()
    if not up:
        return Answer(text="I can't see an upcoming round.", parsed=parsed)
    name = f"round {up['next_round']}"
    cal = cached_calendar(up["season"])
    if cal:
        for r in cal["rounds"]:
            if r["round"] == up["next_round"]:
                name = r["event_name"]
                break
    top = up["predictions"][:3]
    podium = ", ".join(f"{p['driver']} at {p['podium_prob'] * 100:.0f}%" for p in top)
    src = ("off the real qualifying grid" if up["grid_source"] == "qualifying"
           else "from qualifying form, since qualifying hasn't run yet")
    return Answer(text=f"Next up is {name}. The model's podium call is {podium} — {src}.",
                  parsed=parsed, data=up)


def _race_result(s, parsed) -> Answer:
    from f1se.standalone.races import cached_race_card

    season = s.season
    if season is None:
        from f1se.standalone.standings import cached_standings
        st = cached_standings(None)
        season = st["season"] if st else None
    card = cached_race_card(season, s.track) if season else None
    if not card:
        return Answer(text=f"I don't have a result for {s.track} in {season}.", parsed=parsed)
    pod = card.get("actual_podium") or []
    text = (f"{card['event_name']} {season}: {pod[0]} won"
            + (f", from {pod[1]} and {pod[2]}." if len(pod) >= 3 else ".")) if pod else \
           f"I have {card['event_name']} {season} but no podium recorded."
    if card.get("prediction"):
        text += f" The model had {card['prediction']['hit_at_3']} of the 3 right before the race."
    return Answer(text=text, parsed=parsed, data=card)
