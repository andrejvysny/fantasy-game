"""Usage: uv run --with pillow python tools/capture/contact_sheet.py <dir>

Writes <dir>/00_contact_sheet.png: 4-column grid of all PNGs with filename labels.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

COLS = 4
THUMB_W = 384
LABEL_H = 22
PAD = 6
SHEET = "00_contact_sheet.png"


def build(directory: Path) -> Path:
    files = sorted(p for p in directory.glob("*.png") if p.name != SHEET)
    if not files:
        raise SystemExit(f"no PNGs in {directory}")
    thumbs: list[tuple[str, Image.Image]] = []
    for f in files:
        im = Image.open(f).convert("RGB")
        h = round(im.height * THUMB_W / im.width)
        thumbs.append((f.stem, im.resize((THUMB_W, h), Image.LANCZOS)))
    cell_h = max(t.height for _, t in thumbs) + LABEL_H
    rows = (len(thumbs) + COLS - 1) // COLS
    sheet = Image.new(
        "RGB",
        (COLS * (THUMB_W + PAD) + PAD, rows * (cell_h + PAD) + PAD),
        (24, 24, 24),
    )
    draw = ImageDraw.Draw(sheet)
    for i, (label, im) in enumerate(thumbs):
        x = PAD + (i % COLS) * (THUMB_W + PAD)
        y = PAD + (i // COLS) * (cell_h + PAD)
        draw.text((x + 2, y + 4), label, fill=(230, 230, 230))
        sheet.paste(im, (x, y + LABEL_H))
    out = directory / SHEET
    sheet.save(out)
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    print(build(Path(sys.argv[1])))
