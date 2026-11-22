#!/usr/bin/env python3
"""Build the Task 3 reference|render contact sheet without viewing extra images."""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ITEMS = [
    ("Sunflowers", "sunflowers"),
    ("The Snail", "the-snail"),
    ("Composition with Red, Blue and Yellow", "mondrian-1930"),
]
CELL_W, CELL_H = 430, 570
sheet = Image.new("RGB", (CELL_W * 2, CELL_H * 3 + 60), "#eeeae0")
draw = ImageDraw.Draw(sheet)
for row, (title, pid) in enumerate(ITEMS):
    draw.text((12, row * CELL_H + 8), title, fill="#222222")
    draw.text((12, row * CELL_H + 28), "REFERENCE", fill="#666666")
    draw.text((CELL_W + 12, row * CELL_H + 28), "RENDER", fill="#666666")
    for column, path in enumerate((ROOT / "references" / f"{pid}.jpg", ROOT / "recipes" / f"{pid}.png")):
        image = Image.open(path).convert("RGB")
        image.thumbnail((CELL_W - 24, CELL_H - 52))
        x = column * CELL_W + (CELL_W - image.width) // 2
        y = row * CELL_H + 48 + (CELL_H - 52 - image.height) // 2
        sheet.paste(image, (x, y))
output = ROOT / "verification" / "task3-contact-sheet.jpg"
sheet.save(output, quality=92)
print(f"saved {output.relative_to(ROOT)} {sheet.size[0]}x{sheet.size[1]}")
