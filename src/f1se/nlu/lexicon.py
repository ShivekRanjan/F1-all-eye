"""The vocabulary of the domain — how people actually say these things.

Built from the real datasets where possible (track names, driver codes) rather
than typed out, so it can't drift from what the engine will accept. Nobody says
"Emilia Romagna Grand Prix"; they say "Imola". Nobody says "SOFT"; they say
"reds" or "the softs". Every alias here is one a person would plausibly speak
out loud, because the point is to accept real questions, not canonical ones.

Both parsers share this. The rule parser matches against it directly; the
transformer's synthetic training data is generated from it. That is deliberate:
it means the head-to-head measures *parsing*, not who was given a better
dictionary.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

# --- circuits ---------------------------------------------------------------
# Spoken names, nicknames and the city or circuit people actually use. Keys are
# lowercase; the value is the canonical event_name the engine expects.
TRACK_ALIASES: dict[str, str] = {
    "abu dhabi": "Abu Dhabi Grand Prix", "yas marina": "Abu Dhabi Grand Prix",
    "australia": "Australian Grand Prix", "melbourne": "Australian Grand Prix",
    "albert park": "Australian Grand Prix",
    "austria": "Austrian Grand Prix", "red bull ring": "Austrian Grand Prix",
    "spielberg": "Austrian Grand Prix",
    "azerbaijan": "Azerbaijan Grand Prix", "baku": "Azerbaijan Grand Prix",
    "bahrain": "Bahrain Grand Prix", "sakhir": "Bahrain Grand Prix",
    "barcelona": "Barcelona Grand Prix", "catalunya": "Barcelona Grand Prix",
    "belgium": "Belgian Grand Prix", "spa": "Belgian Grand Prix",
    "francorchamps": "Belgian Grand Prix",
    "britain": "British Grand Prix", "silverstone": "British Grand Prix",
    "british": "British Grand Prix", "england": "British Grand Prix",
    "canada": "Canadian Grand Prix", "montreal": "Canadian Grand Prix",
    "gilles villeneuve": "Canadian Grand Prix",
    "china": "Chinese Grand Prix", "shanghai": "Chinese Grand Prix",
    "netherlands": "Dutch Grand Prix", "zandvoort": "Dutch Grand Prix",
    "holland": "Dutch Grand Prix", "dutch": "Dutch Grand Prix",
    "imola": "Emilia Romagna Grand Prix", "emilia": "Emilia Romagna Grand Prix",
    "emilia romagna": "Emilia Romagna Grand Prix",
    "hungary": "Hungarian Grand Prix", "hungaroring": "Hungarian Grand Prix",
    "budapest": "Hungarian Grand Prix",
    "italy": "Italian Grand Prix", "monza": "Italian Grand Prix",
    "japan": "Japanese Grand Prix", "suzuka": "Japanese Grand Prix",
    "las vegas": "Las Vegas Grand Prix", "vegas": "Las Vegas Grand Prix",
    "mexico": "Mexico City Grand Prix", "mexico city": "Mexico City Grand Prix",
    "hermanos rodriguez": "Mexico City Grand Prix",
    "miami": "Miami Grand Prix",
    "monaco": "Monaco Grand Prix", "monte carlo": "Monaco Grand Prix",
    "qatar": "Qatar Grand Prix", "losail": "Qatar Grand Prix",
    "saudi": "Saudi Arabian Grand Prix", "saudi arabia": "Saudi Arabian Grand Prix",
    "jeddah": "Saudi Arabian Grand Prix",
    "singapore": "Singapore Grand Prix", "marina bay": "Singapore Grand Prix",
    "spain": "Spanish Grand Prix", "spanish": "Spanish Grand Prix",
    "brazil": "São Paulo Grand Prix", "sao paulo": "São Paulo Grand Prix",
    "interlagos": "São Paulo Grand Prix",
    "usa": "United States Grand Prix", "austin": "United States Grand Prix",
    "cota": "United States Grand Prix", "united states": "United States Grand Prix",
    "america": "United States Grand Prix",
}

# --- tyres ------------------------------------------------------------------
COMPOUND_ALIASES: dict[str, str] = {
    "soft": "SOFT", "softs": "SOFT", "red": "SOFT", "reds": "SOFT",
    "medium": "MEDIUM", "mediums": "MEDIUM", "yellow": "MEDIUM", "yellows": "MEDIUM",
    "hard": "HARD", "hards": "HARD", "white": "HARD", "whites": "HARD",
}

# --- objectives -------------------------------------------------------------
OBJECTIVE_ALIASES: dict[str, str] = {
    "fastest": "mean", "quickest": "mean", "best": "mean", "optimal": "mean",
    "median": "median", "typical": "median", "average": "median",
    "safe": "p85", "safest": "p85", "conservative": "p85", "risk averse": "p85",
    "risk-averse": "p85", "cautious": "p85",
}

# --- drivers ----------------------------------------------------------------
# Surname -> code. Codes are the engine's key; surnames are what people say.
DRIVER_ALIASES: dict[str, str] = {
    "verstappen": "VER", "max": "VER",
    "hamilton": "HAM", "lewis": "HAM",
    "leclerc": "LEC", "charles": "LEC",
    "russell": "RUS", "george": "RUS",
    "norris": "NOR", "lando": "NOR",
    "piastri": "PIA", "oscar": "PIA",
    "antonelli": "ANT", "kimi": "ANT",
    "alonso": "ALO", "fernando": "ALO",
    "sainz": "SAI", "carlos": "SAI",
    "albon": "ALB", "alex": "ALB",
    "gasly": "GAS", "pierre": "GAS",
    "ocon": "OCO", "esteban": "OCO",
    "stroll": "STR", "lance": "STR",
    "hulkenberg": "HUL", "hülkenberg": "HUL", "nico": "HUL",
    "bottas": "BOT", "valtteri": "BOT",
    "perez": "PER", "pérez": "PER", "checo": "PER",
    "lawson": "LAW", "liam": "LAW",
    "hadjar": "HAD", "bearman": "BEA", "colapinto": "COL",
    "bortoleto": "BOR", "lindblad": "LIN",
}


def strip_accents(s: str) -> str:
    """São Paulo == sao paulo. Nobody types the tilde into a chat box."""
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def normalise(text: str) -> str:
    """Lowercase, de-accent, collapse punctuation to spaces."""
    t = strip_accents(text.lower())
    t = re.sub(r"[^a-z0-9\s.\-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


@lru_cache(maxsize=1)
def track_alias_order() -> list[tuple[str, str]]:
    """Aliases longest-first.

    Order matters: "mexico city" must be tried before "mexico", and "sao paulo"
    before "spa" would otherwise match inside it. Sorting by length descending
    makes the greedy longest match correct without special-casing.
    """
    return sorted(TRACK_ALIASES.items(), key=lambda kv: -len(kv[0]))


def canonical_track(text: str) -> str | None:
    """First circuit mentioned in the text, as the engine names it."""
    t = normalise(text)
    best: tuple[int, str] | None = None
    for alias, canon in track_alias_order():
        i = t.find(alias)
        if i == -1:
            continue
        # Whole-word only: "spa" must not fire inside "space" or "sao paulo".
        before_ok = i == 0 or not t[i - 1].isalnum()
        after = i + len(alias)
        after_ok = after >= len(t) or not t[after].isalnum()
        if before_ok and after_ok and (best is None or i < best[0]):
            best = (i, canon)
    return best[1] if best else None


def all_vocabulary() -> set[str]:
    """Every word the domain uses — the seed for the transformer's tokeniser."""
    words: set[str] = set()
    for d in (TRACK_ALIASES, COMPOUND_ALIASES, OBJECTIVE_ALIASES, DRIVER_ALIASES):
        for k in d:
            words.update(normalise(k).split())
    return words
