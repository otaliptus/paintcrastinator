#!/usr/bin/env python3
"""The Kiss: gold silhouettes, exact ornamental marks, meadow and tender faces."""
import json
import cv2
import numpy as np
from PIL import Image

from plan_intermediate import META, URLS, ROOT, segment, stripes, contours, allocate, colour

pid = "the-kiss"
title, artist, year, _, clusters, description = META[pid]
stroke_count = 2500
source = np.asarray(Image.open(ROOT / "references" / f"{pid}.jpg").convert("RGB"), dtype=np.float32) / 255
h, w = source.shape[:2]
regions, _ = segment(source, pid, clusters)
sx, sy = w / 1000, h / 1000


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
        if area < 8:
            continue
        yy, xx = np.nonzero(masked)
        region = dict(original)
        region.update(mask=masked, area=area, points=np.column_stack([xx, yy]).astype(float))
        cs, _ = cv2.findContours(masked, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if cs:
            region["polygon"] = cv2.approxPolyDP(max(cs, key=cv2.contourArea), 1.2, True).reshape(-1, 2)
            result.append(region)
    return result


def filled(mask, count, diameter=8, coverage=1.5, mode="small"):
    rr = select(mask)
    sets = []
    for region in rr:
        narrow = min(np.ptp(region["points"][:, 0]) + 1, np.ptp(region["points"][:, 1]) + 1)
        sets.append(stripes(region, pid, min(diameter, max(1.6, narrow * .75)), True))
    strokes = allocate(sets, rr, count, mode)
    for stroke in strokes:
        stroke.pop("weight", None)
        stroke["s"] = round(stroke["s"] * coverage, 1)
    return strokes


def dabs(mask, count):
    rr = select(mask)
    def chroma(region):
        c = region["colour"].lstrip("#")
        rgb = [int(c[i:i + 2], 16) for i in (0, 2, 4)]
        return max(rgb) - min(rgb)
    candidates = sorted((r for r in rr if r["area"] <= 1400), key=lambda r: (-chroma(r), r["area"]))
    if len(candidates) < count:
        used = {id(r) for r in candidates}
        candidates += sorted((r for r in rr if id(r) not in used), key=lambda r: r["area"])
    strokes = []
    for region in candidates[:count]:
        x, y = np.mean(region["points"], axis=0)
        strokes.append({"p": [float(x), float(y), float(x + .01), float(y)],
                        "c": region["colour"], "s": round(float(np.clip(np.sqrt(region["area"]) * .7, 1.8, 10)), 1),
                        "o": 1})
    assert len(strokes) == count
    return strokes


def edged(mask, count, coverage=.8):
    rr = select(mask)
    strokes = allocate([contours(region) for region in rr], rr, count, "edges")
    for stroke in strokes:
        stroke.pop("weight", None)
        stroke["s"] = round(max(1.1, stroke["s"]) * coverage, 1)
    return strokes


def single_region(mask, c):
    yy, xx = np.nonzero(mask)
    cs, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    polygon = cv2.approxPolyDP(max(cs, key=cv2.contourArea), 1.5, True).reshape(-1, 2)
    return {"mask": mask, "area": len(xx), "points": np.column_stack([xx, yy]).astype(float), "colour": c, "polygon": polygon, "luminance": .5}


def flat(mask, count, c, diameter=24, coverage=2.3):
    region = single_region(mask, c)
    strokes = allocate([stripes(region, pid, diameter)], [region], count, "area")
    for stroke in strokes:
        stroke.pop("weight", None)
        stroke["s"] = round(stroke["s"] * coverage, 1)
    return strokes


def flat_edges(mask, count, c):
    region = single_region(mask, c)
    strokes = allocate([contours(region)], [region], count, "edges")
    for stroke in strokes:
        stroke.pop("weight", None)
        stroke["c"] = c
        stroke["s"] = 1.6
    return strokes


background = poly([(0, 0), (1000, 0), (1000, 1000), (0, 1000)])
male = poly([(330, 45), (470, 20), (535, 85), (525, 235), (540, 380),
             (510, 570), (505, 850), (320, 875), (285, 760), (280, 410), (295, 175)])
female = poly([(520, 95), (650, 80), (755, 145), (795, 275), (775, 470),
               (755, 710), (710, 875), (505, 860), (510, 570), (540, 380), (525, 235)])
combined = np.maximum(male, female)
meadow = poly([(0, 760), (260, 710), (420, 780), (620, 800), (750, 740),
               (840, 820), (840, 1000), (0, 1000)])
male_face = poly([(340, 55), (425, 45), (495, 85), (490, 145), (430, 175), (350, 135)])
female_face = poly([(535, 115), (615, 105), (675, 155), (650, 230), (565, 235), (520, 175)])
hands = poly([(475, 215), (570, 190), (640, 245), (585, 320), (500, 290)])
people = poly([(340, 30), (475, 20), (540, 75), (650, 80), (715, 135),
               (690, 260), (565, 355), (500, 295), (420, 210), (330, 150)])

bg_pixels = source[round(80 * sy):round(700 * sy), round(850 * sx):round(970 * sx)].reshape(-1, 3)
bg_colour = colour(np.median(bg_pixels, axis=0))
male_colour = colour(np.median(source[male.astype(bool)], axis=0))
female_pixels = source[female.astype(bool)]
female_pixels = female_pixels[(female_pixels[:, 0] > .45) & (female_pixels[:, 1] > .35)]
female_colour = colour(np.median(female_pixels, axis=0))
meadow_colour = colour(np.median(source[meadow.astype(bool)], axis=0))

def skin_colour(mask):
    pixels = source[mask.astype(bool)]
    skin = pixels[(pixels[:, 0] > .5) & (pixels[:, 1] > .4) & (pixels[:, 2] > .3)]
    return colour(np.median(skin if len(skin) else pixels, axis=0))

blocking = (flat(background, 140, bg_colour, 32, 2.4) + flat(meadow, 80, meadow_colour, 22, 2.4)
            + flat(male, 100, male_colour, 22, 2.4) + flat(female, 120, female_colour, 22, 2.4))
form = filled(male, 250, 14, 2.0, "area") + filled(female, 250, 13, 2.0, "area") + filled(meadow, 100, 9, 1.8, "area")
refinement = (filled(male, 350, 6, 1.4) + filled(female, 350, 6, 1.4)
              + filled(meadow, 200, 4, 1.3) + filled(background, 100, 7, 1.4))
detail = (flat(male_face, 20, skin_colour(male_face), 9, 1.4)
          + flat(female_face, 20, skin_colour(female_face), 9, 1.4)
          + flat(hands, 15, skin_colour(hands), 7, 1.4)
          + filled(people, 105, 3, 1.2) + dabs(female, 140)
          + edged(combined, 60, .7) + filled(meadow, 100, 2.8, 1.2))

stages = []
expected = {"blocking": 440, "form": 600, "refinement": 1000, "detail": 460}
for stage_id, label, strokes in [
    ("blocking", "Blocking in", blocking),
    ("form", "Form and colour", form),
    ("refinement", "Refinement", refinement),
    ("detail", "Faces and defining marks", detail),
]:
    assert len(strokes) == expected[stage_id], (stage_id, len(strokes))
    for stroke in strokes:
        stroke["stage"] = stage_id
    stages.append({"id": stage_id, "label": label, "strokes": strokes})

recipe = {
    "id": pid, "title": title, "artist": artist, "year": year,
    "description": description, "width": w, "height": h, "ground": bg_colour,
    "reference": f"../references/{pid}.jpg", "seed": 1908, "profile": "directional-flat",
    "planner": "Opaque gold field; embracing cloak masks; sampled robe ornaments; flower meadow; faces and hands last",
    "credit": {"author": artist, "licence": "Public domain", "source": "Wikimedia Commons", "url": URLS[pid]},
    "strokeCount": stroke_count, "stages": stages,
}
assert sum(len(stage["strokes"]) for stage in stages) == stroke_count
(ROOT / "recipes" / f"{pid}.json").write_text(json.dumps(recipe, separators=(",", ":")) + "\n")
print(f"Planned {pid}: {stroke_count} strokes in four stages")
