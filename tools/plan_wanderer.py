#!/usr/bin/env python3
"""Layered Wanderer: opaque atmospheric underpaint, fog, rocks and crisp figure."""
from pathlib import Path
import json
import cv2
import numpy as np
from PIL import Image

from plan_intermediate import META, URLS, ROOT, segment, stripes, contours, allocate, colour

pid = "wanderer-sea-of-fog"
title, artist, year, stroke_count, clusters, description = META[pid]
source = np.asarray(Image.open(ROOT / "references" / f"{pid}.jpg").convert("RGB"), dtype=np.float32) / 255
h, w = source.shape[:2]
regions, _ = segment(source, pid, 30)
sx, sy = w / 1000, h / 1280


def poly(points):
    mask = np.zeros((h, w), np.uint8)
    pts = np.array([(round(x * sx), round(y * sy)) for x, y in points], np.int32)
    cv2.fillPoly(mask, [pts], 1)
    return mask


def ellipse(cx, cy, rx, ry):
    mask = np.zeros((h, w), np.uint8)
    cv2.ellipse(mask, (round(cx * sx), round(cy * sy)), (round(rx * sx), round(ry * sy)), 0, 0, 360, 1, -1)
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


def filled(mask, count, diameter=22, coverage=2.8, mode="area"):
    rr = select(mask)
    sets = []
    for region in rr:
        narrow = min(np.ptp(region["points"][:, 0]) + 1, np.ptp(region["points"][:, 1]) + 1)
        sets.append(stripes(region, pid, min(diameter, max(2.0, narrow * .68))))
    strokes = allocate(sets, rr, count, mode)
    for stroke in strokes:
        stroke.pop("weight", None)
        stroke["s"] = round(stroke["s"] * coverage, 1)
    return strokes


def edged(mask, count, coverage=1.0):
    rr = select(mask)
    strokes = allocate([contours(region) for region in rr], rr, count, "edges")
    for stroke in strokes:
        stroke.pop("weight", None)
        stroke["s"] = round(max(1.2, stroke["s"]) * coverage, 1)
    return strokes


# Twenty-one overlapping rows guarantee that no dark canvas can leak through.
underpaint = []
rows, columns = 21, 20
for row in range(rows):
    y0, y1 = round(row * h / rows), round((row + 1) * h / rows)
    for column in range(columns):
        x0, x1 = round(column * w / columns), round((column + 1) * w / columns)
        patch = source[y0:y1, x0:x1]
        c = colour(patch.reshape(-1, 3).mean(0))
        inset = (x1 - x0) * .12
        underpaint.append({
            "p": [round(x0 + inset, 1), round((y0 + y1) / 2, 1), round(x1 - inset, 1), round((y0 + y1) / 2, 1)],
            "c": c, "s": round((y1 - y0) * 1.30, 1), "o": 1.0,
        })

figure = poly([(474, 493), (503, 480), (539, 492), (554, 524), (565, 558),
               (594, 572), (617, 604), (596, 640), (582, 623), (575, 696),
               (588, 755), (561, 797), (508, 810), (455, 798), (411, 768),
               (420, 704), (435, 650), (444, 586), (459, 535)])
legs = poly([(444, 754), (490, 766), (482, 825), (462, 857), (445, 899),
             (410, 912), (399, 891), (419, 843), (426, 802)]) | poly(
             [(513, 768), (558, 758), (565, 824), (573, 870), (558, 922),
              (529, 923), (514, 888), (515, 836)])
head = ellipse(502, 457, 42, 43)
whole_figure = np.maximum.reduce([figure, legs, head])
rock = poly([(0, 1280), (0, 1115), (80, 1070), (130, 1095), (198, 1020),
             (240, 1010), (280, 935), (342, 948), (405, 875), (458, 838),
             (510, 813), (554, 836), (609, 908), (665, 949), (719, 934),
             (762, 1000), (803, 1039), (840, 1102), (907, 1082), (960, 1122),
             (1000, 1105), (1000, 1280)])
yy, xx = np.mgrid[:h, :w]
sky = (yy < 505 * sy).astype(np.uint8)
fog = ((yy >= 380 * sy) & (yy < 1150 * sy)).astype(np.uint8)
fog[rock.astype(bool)] = 0
fog[whole_figure.astype(bool)] = 0
far = poly([(0, 625), (0, 498), (75, 495), (155, 466), (250, 381), (292, 373),
            (348, 414), (410, 485), (451, 513), (505, 531), (567, 516),
            (638, 463), (678, 435), (713, 456), (718, 529), (802, 522),
            (865, 503), (931, 504), (1000, 495), (1000, 633), (820, 659),
            (680, 626), (560, 645), (430, 620), (270, 655), (120, 616)])

form = filled(sky, 180, 28, 3.0) + filled(fog, 320, 24, 3.1) + filled(far, 120, 18, 2.6)
refinement = filled(rock, 300, 22, 3.0) + filled(whole_figure, 200, 13, 2.6)
detail = filled(fog, 60, 8, 1.8) + edged(rock, 60, .85) + edged(whole_figure, 100, .8) + filled(head, 40, 5, 1.5)

stages = []
for stage_id, label, strokes in [
    ("blocking", "Blocking in", underpaint),
    ("form", "Form and colour", form),
    ("refinement", "Refinement", refinement),
    ("detail", "Defining marks", detail),
]:
    assert len(strokes) == {"blocking": 420, "form": 620, "refinement": 500, "detail": 260}[stage_id]
    for stroke in strokes:
        stroke["stage"] = stage_id
    stages.append({"id": stage_id, "label": label, "strokes": strokes})

recipe = {
    "id": pid, "title": title, "artist": artist, "year": year,
    "description": description, "width": w, "height": h,
    "ground": colour(source[:round(h * .18)].reshape(-1, 3).mean(0)),
    "reference": f"../references/{pid}.jpg", "seed": 1818, "profile": "directional-flat",
    "planner": "Opaque horizontal underpaint; Lab colour regions; masked atmospheric layers and crisp foreground contours",
    "credit": {"author": artist, "licence": "Public domain", "source": "Wikimedia Commons", "url": URLS[pid]},
    "strokeCount": stroke_count, "stages": stages,
}
(ROOT / "recipes" / f"{pid}.json").write_text(json.dumps(recipe, separators=(",", ":")) + "\n")
print(f"Planned {pid}: {stroke_count} strokes in four stages")
