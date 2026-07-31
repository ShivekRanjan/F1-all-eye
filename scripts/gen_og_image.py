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
LINE = "#1c212b"

FONTS = Path(r"C:\Windows\Fonts")

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# Top accent bar
d.rectangle([0, 0, W, 6], fill=GOLD)

# Badge bars (mirrors the favicon mark)
bx, by = 92, 130
d.rounded_rectangle([bx, by, bx + 32, by + 116], radius=8, fill=GOLD)
d.rounded_rectangle([bx + 40, by, bx + 66, by + 116], radius=6, fill=SOFT)
d.rounded_rectangle([bx + 74, by, bx + 100, by + 116], radius=6, fill=MEDIUM)

display = ImageFont.truetype(str(FONTS / "impact.ttf"), 84)
sub = ImageFont.truetype(str(FONTS / "calibri.ttf"), 34)
small = ImageFont.truetype(str(FONTS / "calibri.ttf"), 24)
mono = ImageFont.truetype(str(FONTS / "consola.ttf"), 24)

y = 300
d.text((bx, y), "F1SE", font=display, fill=INK)
w1 = d.textlength("F1SE", font=display)
d.text((bx + w1 + 14, y + 12), "/", font=display, fill=LINE)
w2 = d.textlength("/", font=display)
d.text((bx + w1 + 14 + w2 + 14, y), "F1 OS", font=display, fill=GOLD)

y2 = y + 110
d.text((bx, y2), "The F1 app that predicts — and shows its work.", font=sub, fill=INK)

y3 = y2 + 58
d.text(
    (bx, y3),
    "Pit-strategy Monte Carlo · podium predictions scored vs reality · live title odds",
    font=small, fill=INK_MUTED,
)

y4 = H - 70
d.text((bx, y4), "github.com/ShivekRanjan/f1-strategy-engine", font=mono, fill=INK_FAINT)

out = Path(__file__).resolve().parents[1] / "frontend" / "public" / "og.png"
img.save(out, "PNG")
print(f"saved {out}")
