#!/usr/bin/env python3
"""Directional flat-region studies for the six Intermediate paintings."""
from pathlib import Path
import argparse
import json
import math

import cv2
import numpy as np
from PIL import Image
from scipy.cluster.vq import kmeans2
from scipy.ndimage import gaussian_filter
from skimage.color import rgb2lab

ROOT = Path(__file__).resolve().parents[1]
STAGES = [("blocking", "Blocking in"), ("form", "Form and colour"), ("refinement", "Refinement"), ("detail", "Defining marks")]
META = {
    "almond-blossom": ("Almond Blossom", "Vincent van Gogh", "1890", 1300, 24, "Turquoise sky surrounds dark curling branches and delicate white blossoms."),
    "woman-with-a-parasol": ("Woman with a Parasol", "Claude Monet", "1875", 1700, 30, "A windblown figure and child stand against a luminous summer sky."),
    "wanderer-sea-of-fog": ("Wanderer above the Sea of Fog", "Caspar David Friedrich", "c. 1818", 1800, 26, "A lone dark figure overlooks layered fog and distant mountains."),
    "cafe-terrace": ("Café Terrace at Night", "Vincent van Gogh", "1888", 1900, 32, "A glowing yellow terrace anchors a deep blue starlit night."),
    "fighting-temeraire": ("The Fighting Temeraire", "J. M. W. Turner", "1839", 1800, 26, "A ghostly ship follows a dark tug through radiant sunset waters."),
    "the-kiss": ("The Kiss", "Gustav Klimt", "1907–08", 1800, 34, "Gold cloaks, patterned robes and tender faces emerge above flowers."),
}
URLS = {
    "almond-blossom": "https://commons.wikimedia.org/wiki/File:Vincent_van_Gogh_-_Almond_Blossom_-_VGM_F671.jpg",
    "woman-with-a-parasol": "https://commons.wikimedia.org/wiki/File:Claude_Monet_-_Woman_with_a_Parasol_-_Madame_Monet_and_Her_Son_-_Google_Art_Project.jpg",
    "wanderer-sea-of-fog": "https://commons.wikimedia.org/wiki/File:Caspar_David_Friedrich_-_Wanderer_above_the_Sea_of_Fog.jpeg",
    "cafe-terrace": "https://commons.wikimedia.org/wiki/File:Van_Gogh_-_Terrasse_des_Caf%C3%A9s_an_der_Place_du_Forum_in_Arles_am_Abend1.jpeg",
    "fighting-temeraire": "https://commons.wikimedia.org/wiki/File:The_Fighting_Temeraire,_JMW_Turner,_National_Gallery.jpg",
    "the-kiss": "https://commons.wikimedia.org/wiki/File:The_Kiss_-_Gustav_Klimt_-_Google_Cultural_Institute.jpg",
}


def colour(values):
    return "#" + "".join(f"{int(np.clip(round(v * 255), 0, 255)):02x}" for v in values)


def rgb(hex_value):
    return np.array([int(hex_value[i:i + 2], 16) for i in (1, 3, 5)], dtype=float) / 255


def segment(source, pid, clusters):
    h, w = source.shape[:2]
    structural = gaussian_filter(source, sigma=(1.05, 1.05, 0))
    lab = rgb2lab(np.clip(structural, 0, 1))
    rng = np.random.default_rng(6100 + len(pid))
    flat = lab.reshape(-1, 3)
    indices = rng.choice(len(flat), size=min(32000, len(flat)), replace=False)
    centres, _ = kmeans2(flat[indices], clusters, iter=40, minit="++", seed=6100)
    labels = np.empty((h, w), np.uint8)
    for y in range(0, h, 48):
        block = lab[y:y + 48].reshape(-1, 3)
        dist = ((block[:, None] - centres[None]) ** 2).sum(-1)
        labels[y:y + 48] = dist.argmin(1).reshape(min(48, h - y), w)
    labels = cv2.medianBlur(labels, 3)
    regions = []
    min_area = 42 if pid in ("almond-blossom", "the-kiss") else 60
    kernel = np.ones((3, 3), np.uint8)
    for cluster in range(clusters):
        clean = (labels == cluster).astype(np.uint8)
        clean = cv2.morphologyEx(clean, cv2.MORPH_CLOSE, kernel)
        count, components, stats, _ = cv2.connectedComponentsWithStats(clean, 8)
        for component in range(1, count):
            area = int(stats[component, cv2.CC_STAT_AREA])
            if area < min_area:
                continue
            mask = (components == component).astype(np.uint8)
            yy, xx = np.nonzero(mask)
            points = np.column_stack([xx, yy]).astype(float)
            pixels = source[yy, xx]
            mean = pixels.mean(0)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            polygon = cv2.approxPolyDP(max(contours, key=cv2.contourArea), 1.8, True).reshape(-1, 2)
            luminance = float(np.dot(mean, [0.2126, 0.7152, 0.0722]))
            regions.append({"mask": mask, "points": points, "area": area, "colour": colour(mean), "polygon": polygon, "luminance": luminance})
    regions.sort(key=lambda r: -r["area"])
    ground = regions[0]["colour"]
    return regions, ground


def direction(pid, region):
    points = region["points"]
    centre = points.mean(0)
    h, w = region["mask"].shape
    x, y = centre / [w, h]
    lum = region["luminance"]
    red, green, blue = rgb(region["colour"])
    if pid == "almond-blossom" and lum > 0.30 and not (red > 0.70 and green > 0.67):
        return 0.0
    if pid == "woman-with-a-parasol":
        if y > 0.67 and green > blue * 0.85:
            return 82.0
        if lum > 0.40 and y < 0.69:
            return -24.0
    if pid in ("wanderer-sea-of-fog", "fighting-temeraire") and lum > 0.20:
        return 0.0
    if pid == "cafe-terrace":
        if y > 0.73:
            return math.degrees(math.atan2(y - 0.54, x - 0.57))
        if blue > red * 1.25:
            return 0.0
    if pid == "the-kiss" and region["area"] > w * h * 0.06:
        return 0.0
    centred = points - centre
    covariance = centred.T @ centred / len(points)
    values, vectors = np.linalg.eigh(covariance)
    vector = vectors[:, np.argmax(values)]
    return math.degrees(math.atan2(vector[1], vector[0]))


def stripes(region, pid, diameter, fine=False):
    """Scan a rotated mask; every run stays clipped inside its colour region."""
    mask = region["mask"]
    h, w = mask.shape
    angle = direction(pid, region)
    theta = math.radians(angle)
    cos, sin = math.cos(theta), math.sin(theta)
    corners = np.array([[-w / 2, -h / 2], [w / 2, -h / 2], [-w / 2, h / 2], [w / 2, h / 2]])
    rotated = corners @ np.array([[cos, sin], [-sin, cos]])
    rw, rh = np.ptp(rotated[:, 0]) + 4, np.ptp(rotated[:, 1]) + 4
    matrix = np.array([[cos, -sin, 0], [sin, cos, 0]], dtype=float)
    matrix[0, 2] = rw / 2 - cos * w / 2 + sin * h / 2
    matrix[1, 2] = rh / 2 - sin * w / 2 - cos * h / 2
    turned = cv2.warpAffine(mask, matrix, (math.ceil(rw), math.ceil(rh)), flags=cv2.INTER_NEAREST)
    spacing = max(2, round(diameter * 0.46))
    inverse = cv2.invertAffineTransform(matrix)
    candidates = []
    for lane in range(0, turned.shape[0], spacing):
        changes = np.diff(np.pad(turned[lane], (1, 1)))
        starts = np.flatnonzero(changes == 1)
        ends = np.flatnonzero(changes == 255)
        for start, end in zip(starts, ends):
            length = int(end - start)
            if length < 2:
                continue
            uv = np.array([[start, lane, 1], [end, lane, 1]], float)
            xy = uv @ inverse.T
            size = min(diameter, max(1.6, length * 0.62))
            candidates.append({"p": [round(xy[0, 0], 1), round(xy[0, 1], 1), round(xy[1, 0], 1), round(xy[1, 1], 1)], "c": region["colour"], "s": round(size, 1), "o": 1.0, "weight": float(length)})
    candidates.sort(key=lambda stroke: -stroke["weight"])
    return candidates


def contours(region):
    polygon = region["polygon"]
    result = []
    for a, b in zip(polygon, np.roll(polygon, -1, axis=0)):
        delta = b.astype(float) - a
        length = float(np.linalg.norm(delta))
        if length < 4:
            continue
        samples = np.linspace(0, 1, max(3, min(16, int(length / 4))))
        sx = np.clip(np.round(a[0] + delta[0] * samples).astype(int), 0, region["mask"].shape[1] - 1)
        sy = np.clip(np.round(a[1] + delta[1] * samples).astype(int), 0, region["mask"].shape[0] - 1)
        if region["mask"][sy, sx].mean() < 0.25:
            continue
        pieces = max(1, min(5, int(length / 48) + 1))
        for piece in range(pieces):
            p = a + delta * (piece / pieces)
            q = a + delta * ((piece + 1) / pieces)
            result.append({"p": [round(float(p[0]), 1), round(float(p[1]), 1), round(float(q[0]), 1), round(float(q[1]), 1)], "c": region["colour"], "s": 2.2, "o": 1.0, "weight": length / pieces})
    return result


def allocate(candidate_sets, regions, count, mode):
    available = [i for i, strokes in enumerate(candidate_sets) if strokes]
    if not available or count <= 0:
        return []
    if mode == "area":
        weights = np.array([regions[i]["area"] for i in available], float)
    elif mode == "edges":
        weights = np.sqrt([regions[i]["area"] for i in available])
    else:
        weights = np.array([1 / math.sqrt(regions[i]["area"]) for i in available])
    targets = weights / weights.sum() * count
    selected = {i: [] for i in available}
    for _ in range(count):
        i = max(available, key=lambda j: targets[available.index(j)] - len(selected[j]))
        source = candidate_sets[i]
        chosen = dict(source[len(selected[i]) % len(source)])
        selected[i].append(chosen)
    ordered = []
    for i in available:
        ordered.extend(selected[i])
    return ordered


def plan(pid):
    title, artist, year, stroke_count, clusters, description = META[pid]
    source = np.asarray(Image.open(ROOT / "references" / f"{pid}.jpg").convert("RGB"), dtype=np.float32) / 255
    h, w = source.shape[:2]
    regions, ground = segment(source, pid, clusters)
    counts = [round(stroke_count * f) for f in (0.27, 0.43, 0.20, 0.10)]
    counts[-1] += stroke_count - sum(counts)
    broad, medium, fine = [], [], []
    for region in regions:
        points = region["points"]
        narrow = min(np.ptp(points[:, 0]) + 1, np.ptp(points[:, 1]) + 1)
        broad.append(stripes(region, pid, min(22, max(3, narrow * 0.62))))
        medium.append(stripes(region, pid, min(9, max(2.2, narrow * 0.32))))
        fine.append(stripes(region, pid, min(3.8, max(1.8, narrow * 0.18)), True))
    edge_sets = [contours(region) for region in regions]
    stage_sets = [broad, medium, edge_sets, fine]
    modes = ["area", "edges", "edges", "small"]
    result = []
    for index, ((stage_id, label), count) in enumerate(zip(STAGES, counts)):
        strokes = allocate(stage_sets[index], regions, count, modes[index])
        for stroke in strokes:
            stroke.pop("weight", None)
            stroke["stage"] = stage_id
        if index == 2:
            strokes.sort(key=lambda s: rgb(s["c"]).mean())
        elif index == 3:
            if pid == "almond-blossom":
                strokes.sort(key=lambda s: rgb(s["c"]).mean())
            elif pid in ("the-kiss", "woman-with-a-parasol", "wanderer-sea-of-fog"):
                strokes.sort(key=lambda s: np.mean([s["p"][1], s["p"][3]]))
        result.append({"id": stage_id, "label": label, "strokes": strokes})
    return {
        "id": pid, "title": title, "artist": artist, "year": year,
        "description": description, "width": w, "height": h, "ground": ground,
        "reference": f"../references/{pid}.jpg", "seed": 6100, "profile": "directional-flat",
        "planner": "CIE Lab connected flat regions; exact regional colours; mask-clipped directional fills and contour strokes",
        "credit": {"author": artist, "licence": "Public domain", "source": "Wikimedia Commons", "url": URLS[pid]},
        "regions": len(regions), "strokeCount": stroke_count, "stages": result,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("painting", choices=list(META))
    args = parser.parse_args()
    recipe = plan(args.painting)
    path = ROOT / "recipes" / f"{args.painting}.json"
    path.write_text(json.dumps(recipe, separators=(",", ":")) + "\n")
    print(f"Planned {args.painting}: {recipe['strokeCount']} strokes, {recipe['regions']} regions, ground {recipe['ground']}")


if __name__ == "__main__":
    main()
