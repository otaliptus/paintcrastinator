#!/usr/bin/env python3
"""Short, hand-paintable recipes for the Painting Cookbook Start here shelf.

References and vector recipes are planned independently. Rendering always uses
app/brush.js through tools/render.mjs; this file never paints the recipe PNG.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
STAGES = [
    ("blocking", "Blocking in", "Block in: big strokes, don't worry about edges."),
    ("form", "Form and color", "Build the large colour and value shapes."),
    ("refinement", "Refinement", "Blend neighbouring values and clarify the simple forms."),
    ("detail", "Fine details", "Finish with the few marks that make the subject recognisable."),
]
META = {
    "lesson-sky": {
        "title": "Sunset over a Still Sea", "artist": "Painting Cookbook lesson", "year": "2026",
        "description": "A sunset distilled to long horizontal bands above a flat, dark sea. Overlapping broad strokes make the colour transitions; two restrained horizon marks finish the scene.",
        "lessonTip": "Teaches blending: overlap long, quiet strokes and let neighbouring colours meet softly.",
    },
    "lesson-sphere": {
        "title": "Orange Ball on a Table", "artist": "Painting Cookbook lesson", "year": "2026",
        "description": "One orange ball explains form in a handful of dabs: warm upper-left light, a deep core shadow, a quieter reflected edge and a cast shadow anchoring it to the table.",
        "lessonTip": "Teaches form: paint the light side, core shadow, reflected light and cast shadow—not just an orange circle.",
    },
    "lesson-hills": {
        "title": "Three Hills in Morning Haze", "artist": "Painting Cookbook lesson", "year": "2026",
        "description": "Three overlapping hill bands demonstrate aerial perspective: the distant ridge is pale and quiet, the middle hill is cooler and darker, and the nearest slope carries the deepest green under a pale morning sky.",
        "lessonTip": "Teaches aerial perspective: distant shapes are lighter and quieter; nearer hills become darker and clearer.",
    },
}
CREDIT = {
    "lesson-sky": {"author": "Painting Cookbook", "licence": "CC0", "source": "CC0 dedication", "url": "https://creativecommons.org/publicdomain/zero/1.0/", "note": "Generated for Painting Cookbook, CC0"},
    "lesson-sphere": {"author": "Painting Cookbook", "licence": "CC0", "source": "CC0 dedication", "url": "https://creativecommons.org/publicdomain/zero/1.0/", "note": "Generated for Painting Cookbook, CC0"},
    "lesson-hills": {"author": "Painting Cookbook", "licence": "CC0", "source": "CC0 dedication", "url": "https://creativecommons.org/publicdomain/zero/1.0/", "note": "Generated for Painting Cookbook, CC0"},
}


def rgb(hex_colour):
    return np.array([int(hex_colour[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)


def colour(values):
    return "#" + "".join(f"{int(np.clip(round(v), 0, 255)):02x}" for v in values)


def stroke(points, c, size, opacity=1.0):
    return {"p": [round(float(v), 1) for v in points], "c": c, "s": round(float(size), 1), "o": round(float(opacity), 2)}


def recipe_shell(pid, width, height, ground, extension="png"):
    recipe = {
        "id": pid, **META[pid], "width": width, "height": height, "ground": ground,
        "reference": f"../references/{pid}.{extension}", "seed": 1729,
        "planner": "short deterministic hand-paintable stroke study",
        "profile": "flat" if pid == "composition-viii" else "lesson",
        "credit": CREDIT[pid], "stages": [],
    }
    return recipe


def add_stages(recipe, groups):
    assert len(groups) == 4
    for (stage_id, label, tip), strokes in zip(STAGES, groups):
        for mark in strokes:
            mark["stage"] = stage_id
        recipe["stages"].append({"id": stage_id, "label": label, "tip": tip, "strokes": strokes})
    recipe["strokeCount"] = sum(len(stage["strokes"]) for stage in recipe["stages"])
    return recipe


def lesson_sky():
    """Twenty broad horizontal marks; the reference is generated, not sourced."""
    pid = "lesson-sky"
    width, height, horizon = 960, 600, 430
    yy = np.arange(height, dtype=float)
    stops = [(0, "#77677f"), (150, "#ba7c78"), (290, "#e99b72"), (430, "#f3ca83")]
    sky = np.zeros((height, 3), dtype=float)
    for (y0, c0), (y1, c1) in zip(stops, stops[1:]):
        mask = (yy >= y0) & (yy <= y1)
        t = np.clip((yy[mask] - y0) / (y1 - y0), 0, 1)[:, None]
        sky[mask] = rgb(c0) * (1 - t) + rgb(c1) * t
    pixels = np.repeat(sky[:, None, :], width, axis=1)
    pixels[horizon:] = rgb("#173f4a")
    pixels[horizon - 2:horizon + 1] = rgb("#102e37")
    reference = Image.fromarray(np.uint8(np.clip(pixels, 0, 255)), "RGB")
    reference.save(ROOT / "references" / f"{pid}.png")

    recipe = recipe_shell(pid, width, height, "#173f4a")
    blocking, form, refinement, detail = [], [], [], []
    for y in np.linspace(22, 405, 8):
        c = colour(sky[int(y)])
        blocking.append(stroke([-20, y, width + 20, y], c, 104, 0.96))
    for y in np.linspace(48, 382, 6):
        c = colour(sky[int(y)])
        form.append(stroke([-15, y, width + 15, y], c, 62, 0.72))
    for y, c in [(458, "#214954"), (500, "#1b424d"), (548, "#173e49"), (586, "#153a45")]:
        refinement.append(stroke([-20, y, width + 20, y], c, 92, 0.90))
    detail.append(stroke([0, horizon - 1, width, horizon - 1], "#183942", 5, 0.95))
    detail.append(stroke([0, horizon + 2, width, horizon + 2], "#102e37", 3, 1.0))
    add_stages(recipe, [blocking, form, refinement, detail])
    recipe["planner"] = "20 horizontal overlapping sky blends, four dark sea bands and two fine horizon strokes"
    assert 20 <= recipe["strokeCount"] <= 40
    return recipe


def lesson_sphere():
    """Forty-eight dabs and bands make one lit ball and its grounding shadow."""
    pid = "lesson-sphere"
    width, height = 960, 600
    cx, cy, radius = 450, 245, 150
    y, x = np.mgrid[0:height, 0:width]
    wall = np.empty((height, width, 3), dtype=float)
    t = np.clip(y / 410, 0, 1)[..., None]
    wall[:] = rgb("#ded3bc") * (1 - t) + rgb("#c9b99d") * t
    wall[390:] = rgb("#bda282")
    # Soft elliptical cast shadow stretches away from the upper-left light.
    ellipse = ((x - 625) / 255) ** 2 + ((y - 442) / 48) ** 2
    shadow_alpha = np.clip((1.12 - ellipse) * 0.55, 0, 0.58)[..., None]
    wall = wall * (1 - shadow_alpha) + rgb("#51463b") * shadow_alpha
    nx, ny = (x - cx) / radius, (y - cy) / radius
    r2 = nx ** 2 + ny ** 2
    nz = np.sqrt(np.clip(1 - r2, 0, 1))
    light = np.array([-0.54, -0.64, 0.55])
    light /= np.linalg.norm(light)
    diffuse = np.clip(nx * light[0] + ny * light[1] + nz * light[2], 0, 1)
    shade = 0.36 + 0.69 * diffuse
    orange = rgb("#dc832e")[None, None, :] * shade[..., None]
    orange += rgb("#9b4a20")[None, None, :] * (1 - diffuse[..., None]) * 0.23
    # A restrained warm reflection returns along the lower-right rim.
    reflection = np.exp(-(((nx - 0.55) / 0.30) ** 2 + ((ny - 0.64) / 0.30) ** 2))
    orange = orange * (1 - 0.25 * reflection[..., None]) + rgb("#d98a43") * (0.25 * reflection[..., None])
    highlight = np.exp(-(((nx + 0.48) / 0.17) ** 2 + ((ny + 0.50) / 0.17) ** 2))
    orange = orange * (1 - 0.65 * highlight[..., None]) + rgb("#ffd58a") * (0.65 * highlight[..., None])
    mask = (r2 <= 1)[..., None]
    pixels = wall * (1 - mask) + orange * mask
    pixels[r2 > 1] = wall[r2 > 1]
    Image.fromarray(np.uint8(np.clip(pixels, 0, 255)), "RGB").save(ROOT / "references" / f"{pid}.png")

    recipe = recipe_shell(pid, width, height, "#c9b99d")
    blocking, form, refinement, detail = [], [], [], []
    for yy in [30, 110, 190, 270, 350]:
        c = colour(pixels[min(389, yy), 40])
        blocking.append(stroke([-20, yy, 980, yy], c, 130, 0.96))
    for yy, c in [(445, "#b79c7c"), (565, "#b69b7b")]:
        blocking.append(stroke([-20, yy, 980, yy], c, 170, 0.96))
    blocking.append(stroke([cx, cy], "#c87328", 300, 1.0))
    for yy, length, size in [(420, 350, 40), (445, 480, 44), (470, 320, 34)]:
        blocking.append(stroke([625 - length / 2, yy, 625 + length / 2, yy], "#655343", size, 0.48))

    light_points = [(375, 130, 78), (335, 205, 88), (390, 225, 86), (455, 145, 72), (350, 295, 78), (420, 315, 70)]
    middle_points = [(455, 235, 82), (450, 300, 78), (505, 185, 72), (420, 355, 58), (500, 285, 68)]
    shadow_points = [(535, 175, 60), (545, 240, 76), (555, 295, 68), (510, 350, 62), (490, 215, 62)]
    for xx, yy, size in light_points + middle_points + shadow_points:
        form.append(stroke([xx, yy], colour(pixels[yy, xx]), size, 0.86))

    ref_points = [(565, 335, 38), (550, 365, 32), (525, 385, 26), (590, 295, 30), (575, 250, 30),
                  (305, 245, 32), (325, 160, 34), (435, 110, 30), (485, 115, 30), (400, 380, 26),
                  (475, 385, 24), (585, 210, 26)]
    for xx, yy, size in ref_points:
        refinement.append(stroke([xx, yy], colour(pixels[yy, xx]), size, 0.74))
    for yy, length in [(430, 360), (450, 410), (475, 230)]:
        refinement.append(stroke([625 - length / 2, yy, 625 + length / 2, yy], "#705a46", 20, 0.38))

    detail.append(stroke([382, 168], "#ffd58a", 34, 0.85))
    detail.append(stroke([400, 145], "#f8bd67", 25, 0.78))
    detail.append(stroke([555, 355], "#d98a43", 23, 0.75))
    detail.append(stroke([574, 325], "#cd7635", 20, 0.72))
    detail.append(stroke([340, 420, 710, 420], "#594b3e", 12, 0.52))
    detail.append(stroke([375, 405, 560, 405], "#806345", 8, 0.55))
    add_stages(recipe, [blocking, form, refinement, detail])
    recipe["planner"] = "48 short-lesson marks: radial colour dabs for light/core/reflected form plus table bands and an elliptical cast shadow"
    assert 40 <= recipe["strokeCount"] <= 70
    return recipe


def lesson_hills():
    """Thirty-one calm marks make three value-separated overlapping ridges."""
    pid = "lesson-hills"
    width, height = 960, 600
    x = np.arange(width, dtype=float)

    def ridge(base, long_amp, long_period, short_amp, short_period, phase):
        return base + long_amp * np.sin(x / long_period + phase) + short_amp * np.sin(x / short_period + phase * 0.37)

    definitions = [
        ("far", ridge(250, 28, 170, 12, 61, 0.4), "#aebdac", 66),
        ("middle", ridge(350, 42, 190, 17, 85, 1.0), "#7f967f", 76),
        ("near", ridge(462, 34, 150, 14, 63, 2.0), "#476955", 86),
    ]
    top = rgb("#dce9e5")[None, :]
    bottom = rgb("#f1e5cd")[None, :]
    yy = np.arange(height, dtype=float)[:, None]
    sky_values = top * (1 - yy / height) + bottom * (yy / height)
    pixels = np.repeat(sky_values[:, None, :], width, axis=1)
    reference = Image.fromarray(np.uint8(np.clip(pixels, 0, 255)), "RGB")
    draw = ImageDraw.Draw(reference)
    for _, top_y, c, _ in definitions:
        polygon = [(int(xx), int(round(y))) for xx, y in zip(x, top_y)] + [(width - 1, height), (0, height)]
        draw.polygon(polygon, fill=c)
    reference.save(ROOT / "references" / f"{pid}.png")

    recipe = recipe_shell(pid, width, height, "#eee2cb")
    blocking, form, refinement, detail = [], [], [], []
    for y in np.linspace(20, 410, 7):
        blocking.append(stroke([-20, y, width + 20, y], colour(sky_values[int(y)]), 112, 0.96))

    for index, (_, top_y, c, diameter) in enumerate(definitions):
        # Broad contour strokes establish each overlap before the next ridge.
        contour_path = []
        for xx in np.linspace(0, width, 10):
            contour_path.extend([xx, float(np.interp(xx, x, top_y))])
        form.append(stroke(contour_path, c, diameter, 1.0))
        lane_min = float(top_y.min() + diameter * 0.42)
        for y in np.arange(lane_min, height + 20, 50):
            inside = y >= top_y
            padded = np.pad(inside.astype(np.uint8), (1, 1))
            changes = np.diff(padded)
            starts = np.flatnonzero(changes == 1)
            ends = np.flatnonzero(changes == 255)
            for start_x, end_x in zip(starts, ends):
                if end_x - start_x > 5:
                    form.append(stroke([start_x - 3, y, end_x + 3, y], c, diameter, 1.0))
        # A fine crest pass clarifies the silhouette without adding detail noise.
        target = detail if index == 2 else refinement
        target.append(stroke(contour_path, c, 24 if index == 0 else 28, 1.0))

    add_stages(recipe, [blocking, form, refinement, detail])
    recipe["planner"] = "31 hand-paintable marks: seven quiet sky blends, horizontal hill fills and one broad plus one fine crest stroke for each overlapping value band"
    assert 30 <= recipe["strokeCount"] <= 60
    return recipe


BUILDERS = {"lesson-sky": lesson_sky, "lesson-sphere": lesson_sphere, "lesson-hills": lesson_hills}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("painting", choices=BUILDERS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    recipe = BUILDERS[args.painting]()
    output = args.output or ROOT / "recipes" / f"{args.painting}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(recipe, separators=(",", ":")) + "\n")
    print(json.dumps({"recipe": str(output), "strokes": recipe["strokeCount"], "stages": [len(s["strokes"]) for s in recipe["stages"]]}))


if __name__ == "__main__":
    main()
