#!/usr/bin/env python3
"""Make one bounded reference|render comparison for Task 6."""
from pathlib import Path
import argparse
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("painting")
parser.add_argument("--suffix", default="")
args = parser.parse_args()
pid = args.painting
width, height = 560, 660
sheet = Image.new("RGB", (width * 2, height + 52), "#eeeae0")
draw = ImageDraw.Draw(sheet)
draw.text((14, 12), pid, fill="#222222")
draw.text((14, 32), "REFERENCE", fill="#666666")
draw.text((width + 14, 32), "RENDER", fill="#666666")
for column, path in enumerate((ROOT / "references" / f"{pid}.jpg", ROOT / "recipes" / f"{pid}.png")):
    image = Image.open(path).convert("RGB")
    image.thumbnail((width - 24, height - 20))
    x = column * width + (width - image.width) // 2
    y = 52 + (height - image.height) // 2
    sheet.paste(image, (x, y))
output = ROOT / "verification" / f"task6-{pid}{args.suffix}-contact.jpg"
sheet.save(output, quality=91)
print(f"saved {output.relative_to(ROOT)}")
