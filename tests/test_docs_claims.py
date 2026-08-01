"""Numbers written in prose must match the numbers in the data.

Code cannot rot quietly because tests run it. Prose can, and did — repeatedly.
Over one working day a reader found four separate stale claims that no check
would ever have caught: a test count a third of the truth, a race count for the
safety-car calibration, screenshots of a UI that no longer existed, and a
documented conclusion the code had already overturned.

Every fix was a one-line edit. The problem was never difficulty, it was that
nothing *looked*. So this file looks: it re-derives each counted claim from the
data or the filesystem and asserts the documents agree.

Deliberately narrow. It checks facts with a single mechanically-checkable
source of truth — counts of things. It does not check prose, conclusions, or
model scores; those need judgement and belong in review. A test that tried to
police them would be noise, and noisy tests get deleted.

Historical documents are exempt by design. A CHANGELOG entry stating the test
count at v1.0.0 is *correct* precisely because it does not track HEAD — a
changelog that updates itself is not a changelog.
"""

from __future__ import annotations

import re
import subprocess
import sys

import pandas as pd
import pytest

from f1se.config import PROJECT_ROOT

PROC = PROJECT_ROOT / "data" / "processed"

#: Files that describe the project as it is now. Anything not listed is either
#: historical (CHANGELOG) or has no counted claims.
LIVE_DOCS = ["README.md", "PROJECT_CONTEXT.md", "docs/METHODOLOGY.md"]


def _races(name: str) -> int:
    return pd.read_parquet(PROC / f"{name}.parquet").groupby(["year", "round"]).ngroups


def _text(rel: str) -> str:
    return (PROJECT_ROOT / rel).read_text(encoding="utf-8")


def test_test_count_claims_match_the_suite():
    """The claim that went stalest: 136 in the docs against 243 in the suite.

    Exact, not approximate. That means adding a test fails this until the README
    is updated, which is the intended cost — a tolerance is just a slower way to
    drift, and the failure message names the file and both numbers.
    """
    # sys.executable, not "python" — the latter resolves to whatever is on PATH,
    # which in a venv-less shell collects a different suite or none at all, and
    # the check then skips silently. A guard that skips when it matters is worse
    # than no guard, because it reads as a pass.
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--collect-only"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    ).stdout
    m = re.search(r"(\d+)\s*/\s*\d+ tests collected", out) or re.search(r"(\d+) tests collected", out)
    if not m:
        pytest.skip("could not read the collected-test count")
    actual = int(m.group(1))

    for rel in LIVE_DOCS:
        for claimed in re.findall(r"(\d{2,4}) no-network tests", _text(rel)):
            assert int(claimed) == actual, (
                f"{rel} claims {claimed} no-network tests; the suite collects {actual}")


@pytest.mark.parametrize("dataset,phrase", [
    ("track_status", r"(\d{2,3}) races of per-lap track-status"),
    ("track_status", r"measured\*\* from (\d{2,3}) races of track-status"),
])
def test_race_count_claims_match_the_data(dataset, phrase):
    actual = _races(dataset)
    for rel in LIVE_DOCS:
        for claimed in re.findall(phrase, _text(rel)):
            assert int(claimed) == actual, (
                f"{rel} claims {claimed} races for {dataset}; the parquet holds {actual}")


def test_view_count_claims_match_the_frontend():
    views = len([p for p in (PROJECT_ROOT / "frontend" / "src" / "views").glob("*.tsx")
                 if p.stem != "common"])
    for rel in LIVE_DOCS:
        for claimed in re.findall(r"(\d{1,2})[- ](?:view|section) React app", _text(rel)):
            assert int(claimed) == views, (
                f"{rel} claims a {claimed}-view app; frontend/src/views holds {views}")


def test_lap_count_claims_match_the_dataset():
    laps = len(pd.read_parquet(PROC / "dry_laps.parquet"))
    for rel in LIVE_DOCS:
        for claimed in re.findall(r"([\d,]{5,7}) (?:race )?laps\b", _text(rel)):
            n = int(claimed.replace(",", ""))
            # Prose rounds ("71,000 laps", "71k"); allow 2% but catch a stale
            # figure from a dataset two ingests ago.
            assert abs(n - laps) / laps < 0.02, (
                f"{rel} claims {claimed} laps; dry_laps.parquet holds {laps:,}")


def test_the_shipped_parser_is_described_correctly():
    """§15 concluded three different things before the one that held. The docs
    tracked the last of those only after a reader pointed out they hadn't."""
    from f1se.nlu import parse

    shipped = parse("who leads the championship").parser
    readme = _text("README.md")
    assert shipped == "hybrid"
    assert "composition of the two ships" in readme, (
        "README no longer states which parser ships; it has been wrong before")


def test_no_live_doc_references_the_removed_streamlit_app():
    """It was replaced by the React client in 2c3fbf6. A live doc implying it
    still exists misdescribes the architecture."""
    for rel in LIVE_DOCS:
        for i, line in enumerate(_text(rel).splitlines(), 1):
            if "Streamlit" not in line:
                continue
            # Past-tense history is fine and worth keeping; present-tense is not.
            assert re.search(r"replaced|swapped|previously|removed|old\b|migrat", line, re.I), (
                f"{rel}:{i} mentions Streamlit outside a historical clause: {line.strip()!r}")
