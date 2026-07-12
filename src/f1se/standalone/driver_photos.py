"""Wikimedia headshots for the V2 driver avatars.

Every photo is pulled through Wikipedia's REST summary API (which resolves to
a Wikimedia-Commons-hosted file), then the Commons file page is checked for a
free licence (CC-BY / CC-BY-SA / CC0 / public domain) before downloading —
anything else (fair-use, unclear, no licence found) is skipped and the UI
falls back to the initials avatar. Attribution for every photo actually used
is written to ``ATTRIBUTIONS.md``.

Run: python -m f1se.standalone.driver_photos
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import pandas as pd
import requests

from f1se.config import PROJECT_ROOT

PROCESSED = PROJECT_ROOT / "data" / "processed"
OUT_DIR = PROJECT_ROOT / "frontend" / "public" / "drivers"
ATTRIBUTIONS = PROJECT_ROOT / "ATTRIBUTIONS.md"

UA = {"User-Agent": "f1-strategy-engine/1.0 (portfolio project; contact via GitHub)"}

# Free-culture licences we're willing to redistribute a resized copy under
# (Commons renders these as "CC BY-SA 4.0", "CC0", "Public domain", ...).
FREE_LICENSES = re.compile(r"cc[\s-]?by([\s-]?sa)?[\s-]?\d|cc0|public domain|pd-|ogl", re.I)

# A few drivers whose Wikipedia article title doesn't match "<FullName>"
# (disambiguation pages, alternate spellings).
TITLE_OVERRIDES = {
    "Kimi Antonelli": "Andrea Kimi Antonelli",
    "Nico Hulkenberg": "Nico Hülkenberg",
    "George Russell": "George Russell (racing driver)",
    "Carlos Sainz": "Carlos Sainz Jr.",
}


def _wikipedia_summary(title: str) -> dict | None:
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(title)}"
    r = requests.get(url, headers=UA, timeout=15)
    if r.status_code != 200:
        return None
    return r.json()


def _commons_license(file_title: str) -> dict | None:
    r = requests.get(
        "https://commons.wikimedia.org/w/api.php",
        params={
            "action": "query", "titles": file_title, "prop": "imageinfo",
            "iiprop": "extmetadata|url", "format": "json",
        },
        headers=UA, timeout=15,
    )
    if r.status_code != 200:
        return None
    pages = r.json().get("query", {}).get("pages", {})
    for p in pages.values():
        info = p.get("imageinfo")
        if not info:
            continue
        meta = info[0].get("extmetadata", {})
        license_short = meta.get("LicenseShortName", {}).get("value", "")
        artist = re.sub("<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip()
        return {
            "license": license_short,
            "artist": artist or "Wikimedia Commons",
            "url": info[0].get("descriptionurl", ""),
        }
    return None


def _existing_photo(code: str) -> Path | None:
    for ext in ("jpg", "jpeg", "png", "webp"):
        p = OUT_DIR / f"{code}.{ext}"
        if p.exists():
            return p
    return None


def _load_prior_attributions() -> dict[str, dict]:
    """Re-usable rows from a previous run, keyed by code, so a re-run for the
    stragglers (rate-limited last time) doesn't drop already-fetched credits."""
    if not ATTRIBUTIONS.exists():
        return {}
    prior: dict[str, dict] = {}
    for line in ATTRIBUTIONS.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ") or line.startswith("| Driver"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 5:
            continue
        name_code, file, license_, artist, source = cells
        m = re.match(r"(.+) \(([A-Z]{3})\)$", name_code)
        if not m:
            continue
        name, code = m.group(1), m.group(2)
        prior[code] = {
            "code": code, "name": name, "file": file,
            "license": license_, "artist": artist, "source": source,
        }
    return prior


def fetch_driver_photos(driver_info_path: Path | None = None) -> list[dict]:
    df = pd.read_parquet(driver_info_path or PROCESSED / "driver_info.parquet")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prior = _load_prior_attributions()
    attributions: list[dict] = []

    for row in df.itertuples(index=False):
        code, name = str(row.driver), str(row.full_name)
        if code in prior and _existing_photo(code):
            attributions.append(prior[code])
            print(f"  {code}: already have {prior[code]['file']} — skipping", flush=True)
            continue
        title = TITLE_OVERRIDES.get(name, name)
        try:
            summary = _wikipedia_summary(title)
            if not summary or "originalimage" not in summary:
                print(f"  {code}: no Wikipedia image — initials fallback", flush=True)
                continue
            img_url = summary["originalimage"]["source"]
            raw_name = requests.utils.unquote(img_url.rsplit("/", 1)[-1].split("?")[0])
            file_name = "File:" + raw_name
            lic = _commons_license(file_name)
            if not lic or not FREE_LICENSES.search(lic["license"]):
                print(f"  {code}: licence '{lic and lic['license']}' not free — skipped", flush=True)
                continue
            img = None
            for attempt, wait in enumerate((0, 3, 8)):
                if wait:
                    time.sleep(wait)
                resp = requests.get(img_url, headers=UA, timeout=20)
                if resp.status_code == 429:
                    continue
                resp.raise_for_status()
                img = resp
                break
            if img is None:
                print(f"  {code}: still rate-limited after retries — initials fallback", flush=True)
                continue
            ext = img_url.rsplit(".", 1)[-1].split("?")[0].lower()
            ext = ext if ext in ("jpg", "jpeg", "png", "webp") else "jpg"
            dest = OUT_DIR / f"{code}.{ext}"
            dest.write_bytes(img.content)
            attributions.append({
                "code": code, "name": name, "file": dest.name,
                "license": lic["license"], "artist": lic["artist"], "source": lic["url"],
            })
            print(f"  {code}: saved {dest.name} ({lic['license']}, {lic['artist']})", flush=True)
        except Exception as e:  # pragma: no cover - network
            print(f"  {code}: error {e} — initials fallback", flush=True)
        time.sleep(1.0)  # be polite to the API

    lines = [
        "# Photo attributions",
        "",
        "Driver headshots are pulled from Wikimedia Commons under free licences.",
        "Drivers without a free-licensed photo fall back to an initials avatar.",
        "",
        "| Driver | File | Licence | Author | Source |",
        "|---|---|---|---|---|",
    ]
    for a in attributions:
        lines.append(
            f"| {a['name']} ({a['code']}) | {a['file']} | {a['license']} | {a['artist']} | {a['source']} |"
        )
    ATTRIBUTIONS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"DONE: {len(attributions)}/{len(df)} photos -> {OUT_DIR}, attributions -> {ATTRIBUTIONS}", flush=True)
    return attributions


if __name__ == "__main__":
    fetch_driver_photos()
