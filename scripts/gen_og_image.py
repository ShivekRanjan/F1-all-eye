"""Regenerate frontend/public/og.png in the V2 gold palette.

One-off asset script (not part of the package) — run with the venv's Python
whenever the brand palette changes. Uses local Windows fonts as stand-ins for
the web fonts (Impact for the Archivo Black wordmark, Consolas for mono).
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
BG = "#06070a"
GOLD = "#d4af37"
SOFT = "#ff2b2b"
MEDIUM = "#f6c700"
INK = "#eef1f5"
INK_MUTED = "#aab3c0"
INK_FAINT = "#7d8698"

FONTS = Path(r"C:\Windows\Fonts")

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# Top accent bar
d.rectangle([0, 0, W, 6], fill=GOLD)

# Badge: the folded-flag chevron, same shape as favicon.svg and the app's
# <Logo/>. Was three bars, which matched neither — the tab icon said one thing
# and the sidebar another, and nobody noticed for two months.
bx, by = 92, 130
BADGE = 116
d.rounded_rectangle([bx, by, bx + BADGE, by + BADGE], radius=26,
                    fill="#151109", outline="#3a3020", width=3)
# polygon(0 0, 100% 25%, 100% 100%, 0 75%), inset into the badge
ix, iy, iw = bx + 30, by + 26, 46
d.polygon(
    [(ix, iy), (ix + iw, iy + int(iw * 0.26)), (ix + iw, iy + BADGE - 52), (ix, iy + BADGE - 64)],
    fill=GOLD,
)

display = ImageFont.truetype(str(FONTS / "impact.ttf"), 84)
sub = ImageFont.truetype(str(FONTS / "calibri.ttf"), 34)
small = ImageFont.truetype(str(FONTS / "calibri.ttf"), 24)
mono = ImageFont.truetype(str(FONTS / "consola.ttf"), 24)

y = 300
d.text((bx, y), "F1SE", font=display, fill=INK)
w1 = d.textlength("F1SE", font=display)
# No vertical offset on the separator. Impact's "/" inks 17..86 against the
# wordmark's 18..86 at the same baseline — centres 51.5 vs 52.0, i.e. already
# aligned. An earlier +12 nudge pushed it visibly below the text; it was solving
# a problem the font does not have.
#
# INK_FAINT, not LINE: LINE (#1c212b) is the border token and renders as a
# near-invisible smudge on the near-black card. The app's own wordmark separator
# is ink-faint, so this now matches it.
d.text((bx + w1 + 14, y), "/", font=display, fill=INK_FAINT)
w2 = d.textlength("/", font=display)
d.text((bx + w1 + 14 + w2 + 14, y), "F1 OS", font=display, fill=GOLD)

y2 = y + 110
d.text((bx, y2), "The F1 app that predicts — and shows its work.", font=sub, fill=INK)

y3 = y2 + 58
# Three claims, chosen because each is checkable and none is a feature list:
# the simulation, the fact that predictions are scored against what happened,
# and the plain-English layer — the one thing a reader cannot guess from
# "F1 dashboard".
d.text(
    (bx, y3),
    "Monte-Carlo pit strategy · predictions scored against reality · ask it in plain English",
    font=small, fill=INK_MUTED,
)

y4 = H - 70
d.text((bx, y4), "github.com/ShivekRanjan/f1-strategy-engine", font=mono, fill=INK_FAINT)

out = Path(__file__).resolve().parents[1] / "frontend" / "public" / "og.png"
img.save(out, "PNG")
print(f"saved {out}")
