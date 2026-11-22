#!/usr/bin/env python3
"""Café Terrace: opaque night ground, warm architecture and perspective paving."""
import json
import math
import cv2
import numpy as np
from PIL import Image

from plan_intermediate import META, URLS, ROOT, segment, stripes, contours, allocate, colour

pid = "cafe-terrace"
title, artist, year, stroke_count, clusters, description = META[pid]
source = np.asarray(Image.open(ROOT / "references" / f"{pid}.jpg").convert("RGB"), dtype=np.float32) / 255
h, w = source.shape[:2]
regions, _ = segment(source, pid, 34)
sx, sy = w / 1000, h / 1280


def poly(points):
    mask = np.zeros((h, w), np.uint8)
    pts = np.array([(round(x * sx), round(y * sy)) for x, y in points], np.int32)
    cv2.fillPoly(mask, [pts], 1)
    return mask


def select(mask):
    result = []
    for original in regions:
        masked = cv2.bitwise_and(original["mask"], mask)
        area = int(masked.sum())
        if area < 12:
            continue
        yy, xx = np.nonzero(masked)
        region = dict(original)
        region.update(mask=masked, area=area, points=np.column_stack([xx, yy]).astype(float))
        cs, _ = cv2.findContours(masked, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if cs:
            region["polygon"] = cv2.approxPolyDP(max(cs, key=cv2.contourArea), 1.5, True).reshape(-1, 2)
            result.append(region)
    return result


def filled(mask, count, diameter=20, coverage=2.7, mode="area"):
    rr = select(mask)
    sets = []
    for region in rr:
        narrow = min(np.ptp(region["points"][:, 0]) + 1, np.ptp(region["points"][:, 1]) + 1)
        sets.append(stripes(region, pid, min(diameter, max(2.0, narrow * .65))))
    strokes = allocate(sets, rr, count, mode)
    for stroke in strokes:
        stroke.pop("weight", None)
        stroke["s"] = round(stroke["s"] * coverage, 1)
    return strokes


def edged(mask, count, coverage=.9):
    rr = select(mask)
    strokes = allocate([contours(region) for region in rr], rr, count, "edges")
    for stroke in strokes:
        stroke.pop("weight", None)
        stroke["s"] = round(max(1.2, stroke["s"]) * coverage, 1)
    return strokes


# Opaque rectangular colour sampling prevents gaps between later regional strokes.
underpaint = []
rows, columns = 20, 20
for row in range(rows):
    y0, y1 = round(row * h / rows), round((row + 1) * h / rows)
    for column in range(columns):
        x0, x1 = round(column * w / columns), round((column + 1) * w / columns)
        c = colour(source[y0:y1, x0:x1].reshape(-1, 3).mean(0))
        inset = (x1 - x0) * .10
        underpaint.append({"p": [round(x0 + inset, 1), round((y0 + y1) / 2, 1), round(x1 - inset, 1), round((y0 + y1) / 2, 1)], "c": c, "s": round((y1 - y0) * 1.32, 1), "o": 1.0})

yy, xx = np.mgrid[:h, :w]
sky = (yy < 430 * sy).astype(np.uint8)
terrace = poly([(0, 190), (120, 170), (220, 220), (365, 200), (500, 245),
                (620, 345), (655, 505), (605, 675), (585, 807), (450, 825),
                (300, 789), (130, 810), (0, 821)])
awning = poly([(0, 448), (120, 423), (260, 392), (400, 405), (535, 438),
               (623, 505), (593, 581), (480, 560), (340, 535), (170, 558), (0, 568)])
warm = np.maximum(terrace, awning)
dark_right = poly([(635, 225), (753, 175), (1000, 167), (1000, 813), (855, 790),
                   (750, 730), (680, 671), (617, 579)])
street = (yy > (760 * sy + np.maximum(0, xx - 580 * sx) * .16)).astype(np.uint8)
left = poly([(0, 220), (90, 205), (130, 330), (115, 700), (0, 752)])
figures = poly([(118, 622), (195, 578), (306, 585), (421, 560), (525, 616),
                (548, 735), (443, 788), (285, 775), (143, 746)])

form = filled(sky, 150, 30, 3.0) + filled(warm, 180, 24, 3.0) + filled(dark_right, 130, 22, 2.8) + filled(street, 140, 25, 3.0)
refinement = filled(warm, 240, 15, 2.4) + filled(dark_right, 100, 13, 2.2) + filled(street, 190, 14, 2.4) + filled(left, 20, 12, 2.0)

# A small star field is deliberately reserved for the last stage.
stars = []
star_positions = [(665, 76), (714, 126), (760, 75), (805, 151), (846, 82),
                  (899, 128), (942, 68), (700, 224), (783, 250), (889, 250),
                  (929, 320), (834, 331)]
for index, (x, y) in enumerate(star_positions):
    px, py = x * sx, y * sy
    stars.append({"p": [round(px - 3.0, 1), round(py, 1), round(px + 3.0, 1), round(py, 1)], "c": "#f6dfa0" if index % 3 else "#efe8bd", "s": 5.0 + index % 3, "o": 1.0})
sky_spark = filled(sky, 18, 5, 1.2, "small")
detail = stars + sky_spark + edged(warm, 100, .85) + filled(street, 120, 7, 1.45) + edged(figures, 100, .8)

stages = []
expected = {"blocking": 400, "form": 600, "refinement": 550, "detail": 350}
for stage_id, label, strokes in [
    ("blocking", "Blocking in", underpaint),
    ("form", "Form and colour", form),
    ("refinement", "Refinement", refinement),
    ("detail", "Defining marks", detail),
]:
    assert len(strokes) == expected[stage_id], (stage_id, len(strokes))
    for stroke in strokes:
        stroke["stage"] = stage_id
    stages.append({"id": stage_id, "label": label, "strokes": strokes})

recipe = {
    "id": pid, "title": title, "artist": artist, "year": year,
    "description": description, "width": w, "height": h,
    "ground": colour(source[:round(h * .16)].reshape(-1, 3).mean(0)),
    "reference": f"../references/{pid}.jpg", "seed": 1888, "profile": "directional-flat",
    "planner": "Opaque sampled underpaint; Lab colour regions; warm architectural masks and perspective-directed paving",
    "credit": {"author": artist, "licence": "Public domain", "source": "Wikimedia Commons", "url": URLS[pid]},
    "strokeCount": stroke_count, "stages": stages,
}
(ROOT / "recipes" / f"{pid}.json").write_text(json.dumps(recipe, separators=(",", ":")) + "\n")
print(f"Planned {pid}: {stroke_count} strokes in four stages")
