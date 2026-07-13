"""Driver cutouts: transparent-background portrait crops for the V2 podium
hero treatment (real F1-broadcast-style cutouts, not a cropped circle).

Re-fetches each driver's already license-verified Wikimedia photo at full
resolution — the committed avatar photos (frontend/public/drivers/*.jpg) are
small 240px center-cropped squares, too low-res and too tightly cropped for
clean matting — and runs background removal (rembg / U2Net) to produce the
cutout. Committed as PNG with alpha under frontend/public/drivers/cutouts/.

Not a runtime dependency of the app: `pip install rembg onnxruntime` ad-hoc
before running this, it's a one-off asset-generation script.

Run: python -m f1se.standalone.driver_cutouts
"""

from __future__ import annotations

import io
import time
from pathlib import Path

import pandas as pd
import requests
from PIL import Image

from f1se.config import PROJECT_ROOT
from f1se.standalone.driver_photos import (
    FREE_LICENSES,
    TITLE_OVERRIDES,
    UA,
    _commons_license,
    _wikipedia_summary,
)

OUT_DIR = PROJECT_ROOT / "frontend" / "public" / "drivers" / "cutouts"
MAX_HEIGHT = 640  # cap output size — these are hero-sized, not thumbnails, but no need for huge files


def build_cutout(code: str, name: str) -> bool:
    from rembg import remove  # imported lazily — not a project dependency

    title = TITLE_OVERRIDES.get(name, name)
    summary = _wikipedia_summary(title)
    if not summary or "originalimage" not in summary:
        return False
    img_url = summary["originalimage"]["source"]
    raw_name = requests.utils.unquote(img_url.rsplit("/", 1)[-1].split("?")[0])
    file_name = "File:" + raw_name
    lic = _commons_license(file_name)
    if not lic or not FREE_LICENSES.search(lic["license"]):
        return False

    resp = None
    for wait in (0, 4, 10):
        if wait:
            time.sleep(wait)
        r = requests.get(img_url, headers=UA, timeout=30)
        if r.status_code == 429:
            continue
        r.raise_for_status()
        resp = r
        break
    if resp is None:
        raise RuntimeError("rate-limited after retries")
    src = Image.open(io.BytesIO(resp.content)).convert("RGB")
    cutout = remove(src)

    w, h = cutout.size
    if h > MAX_HEIGHT:
        scale = MAX_HEIGHT / h
        cutout = cutout.resize((round(w * scale), MAX_HEIGHT), Image.LANCZOS)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # WebP, not PNG: these are full photographic cutouts (not flat-color
    # graphics), where PNG barely compresses — lossy WebP at this quality is
    # visually identical but ~8x smaller (measured: 8.8MB -> 1.1MB for 24).
    cutout.save(OUT_DIR / f"{code}.webp", "WEBP", quality=85)
    return True


def build_all(driver_info_path: Path | None = None) -> None:
    df = pd.read_parquet(driver_info_path or PROJECT_ROOT / "data" / "processed" / "driver_info.parquet")
    ok = 0
    for row in df.itertuples(index=False):
        code, name = str(row.driver), str(row.full_name)
        dest = OUT_DIR / f"{code}.webp"
        if dest.exists():
            print(f"  {code}: already have cutout — skipping", flush=True)
            ok += 1
            continue
        try:
            if build_cutout(code, name):
                ok += 1
                print(f"  {code}: cutout saved", flush=True)
            else:
                print(f"  {code}: no free-licensed image — skipped", flush=True)
        except Exception as e:  # pragma: no cover - network / model
            print(f"  {code}: error {e} — skipped", flush=True)
        time.sleep(2.0)  # be polite to the Wikipedia/Commons APIs
    print(f"DONE: {ok}/{len(df)} cutouts -> {OUT_DIR}", flush=True)


if __name__ == "__main__":
    build_all()
