"""Assemble the README hero GIF from a folder of screenshots.

    python scripts/make_demo_gif.py shots/            # -> assets/demo.gif
    python scripts/make_demo_gif.py shots/ --hold 2.4 --width 1100

Frames are ordered by filename, so name them `01-home.png`, `02-ask.png`, and so
on. Anything the browser produces will do — each shot is scaled to cover the
target box and centre-cropped, so mixed sizes and a stray toolbar are fine.

Why a script rather than a screen recorder: the hero is a slideshow of stills,
not a capture. Stills stay legible at README width, weigh a tenth of a recording,
and can be regenerated one frame at a time when a single view changes — which is
what actually happens. The previous hero was assembled by hand and went stale for
three weeks because redoing it meant redoing all of it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from f1se.config import PROJECT_ROOT

OUT = PROJECT_ROOT / "assets" / "demo.gif"
#: Matches the hero it replaces. 16:9, so a full-screen or maximised-window
#: capture scales in without cropping anything away.
SIZE = (1100, 618)
EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def load_frames(folder: Path, size: tuple[int, int]) -> list[Image.Image]:
    paths = sorted(p for p in folder.iterdir() if p.suffix.lower() in EXTS)
    if not paths:
        raise SystemExit(f"no images in {folder} (looked for {', '.join(sorted(EXTS))})")

    frames = []
    for p in paths:
        im = Image.open(p).convert("RGB")
        # Scale to *cover*, then centre-crop — letterboxing would put black bars
        # on a hero image, and squashing would misrepresent the layout.
        scale = max(size[0] / im.width, size[1] / im.height)
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        left, top = (im.width - size[0]) // 2, (im.height - size[1]) // 2
        frames.append(im.crop((left, top, left + size[0], top + size[1])))
        print(f"  {p.name:28} {Image.open(p).size} -> {size}")
    return frames


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path, help="directory of screenshots, ordered by filename")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--hold", type=float, default=2.4, help="seconds per frame")
    ap.add_argument("--width", type=int, default=SIZE[0])
    ap.add_argument("--colors", type=int, default=200,
                    help="palette size; drop it if the file comes out too heavy")
    args = ap.parse_args()

    size = (args.width, round(args.width * SIZE[1] / SIZE[0]))
    frames = load_frames(args.folder, size)

    # An adaptive palette per frame keeps the gold/cyan accent from banding into
    # mud, which a web-safe palette does immediately on these dark surfaces.
    quantized = [f.quantize(colors=args.colors, method=Image.MEDIANCUT) for f in frames]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    quantized[0].save(
        args.out, save_all=True, append_images=quantized[1:],
        duration=int(args.hold * 1000), loop=0, optimize=True, disposal=2,
    )

    kb = args.out.stat().st_size / 1024
    print(f"\n{args.out}  {len(frames)} frames  {size[0]}x{size[1]}  {kb:.0f} KB")
    if kb > 5000:
        print("!! over 5 MB — GitHub will serve it slowly. Try --colors 128 or fewer frames.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
