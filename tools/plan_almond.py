#!/usr/bin/env python3
"""Layered Almond Blossom: smooth sky, curved branch paths, blossom dabs."""
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.cluster.vq import kmeans2
from scipy.ndimage import gaussian_filter
from skimage.color import rgb2lab
from skimage.morphology import skeletonize

from plan_intermediate import META, URLS, ROOT, colour, stripes, allocate, rgb


def components(mask, source, min_area=4):
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    regions = []
    for index in range(1, count):
        if stats[index, cv2.CC_STAT_AREA] < min_area:
            continue
        item = (labels == index).astype(np.uint8)
        yy, xx = np.nonzero(item)
        mean = source[yy, xx].mean(0)
        regions.append({"mask": item, "points": np.column_stack([xx, yy]).astype(float), "area": len(xx), "colour": colour(mean), "luminance": float(np.dot(mean, [0.2126, 0.7152, 0.0722])), "polygon": np.empty((0, 2))})
    return regions


def colour_regions(mask, source, count=9):
    yy, xx = np.nonzero(mask)
    pixels = source[yy, xx]
    lab = rgb2lab(pixels.reshape(1, -1, 3)).reshape(-1, 3)
    centres, labels = kmeans2(lab, count, iter=25, minit="++", seed=1890)
    regions = []
    for index in range(count):
        selected = np.zeros(mask.shape, np.uint8)
        selected[yy[labels == index], xx[labels == index]] = 1
        selected = cv2.morphologyEx(selected, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
        regions.extend(components(selected, source, 7))
    return regions


def skeleton_paths(mask, source, budget):
    mask = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    distance = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    skeleton = skeletonize(mask > 0)
    points = set(zip(*np.nonzero(skeleton)))
    offset = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
    paths = []
    visited = set()
    for start in sorted(points):
        neighbours = ((start[0] + dy, start[1] + dx) for dy, dx in offset)
        degree = sum(p in points for p in neighbours)
        if degree == 2:
            continue
        for dy, dx in offset:
            nxt = (start[0] + dy, start[1] + dx)
            edge = tuple(sorted((start, nxt)))
            if nxt not in points or edge in visited:
                continue
            visited.add(edge)
            path = [start, nxt]
            previous, current = start, nxt
            while True:
                choices = []
                for ndy, ndx in offset:
                    candidate = (current[0] + ndy, current[1] + ndx)
                    next_edge = tuple(sorted((current, candidate)))
                    if candidate in points and candidate != previous and next_edge not in visited:
                        choices.append(candidate)
                if not choices:
                    break
                following = choices[0]
                visited.add(tuple(sorted((current, following))))
                path.append(following)
                previous, current = current, following
            if len(path) >= 5:
                paths.append(path)
    paths.sort(key=len, reverse=True)
    strokes = []
    for path in paths:
        if len(strokes) >= budget:
            break
        stride = max(2, len(path) // 12)
        sampled = path[::stride]
        if sampled[-1] != path[-1]:
            sampled.append(path[-1])
        coords = np.array(sampled)[:, ::-1].astype(float)
        pixels = np.array([source[y, x] for y, x in path[::max(1, len(path) // 10)]])
        diameter = float(np.clip(np.median([distance[y, x] for y, x in path]) * 1.75, 2.8, 11.0))
        p = [round(float(v), 1) for point in coords for v in point]
        strokes.append({"p": p, "c": colour(pixels.mean(0)), "s": round(diameter, 1), "o": 1.0, "stage": "refinement"})
    return strokes


def plan():
    pid = "almond-blossom"
    title, artist, year, total, _, description = META[pid]
    source = np.asarray(Image.open(ROOT / "references" / f"{pid}.jpg").convert("RGB"), dtype=np.float32) / 255
    h, w = source.shape[:2]
    red, green, blue = source.transpose(2, 0, 1)
    luminance = np.dot(source, [0.2126, 0.7152, 0.0722])
    sky = (green > red * 1.075) & (blue > red * 1.04) & (blue > 0.22) & (luminance > 0.25)
    sky = cv2.morphologyEx(sky.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)) > 0
    branch = ((~sky) & (luminance < 0.66)) | ((luminance < 0.31) & (blue < green * 1.15))
    branch &= luminance < 0.69
    blossom = ((~sky) & ~branch & (luminance > 0.48)) | ((red > 0.57) & (green > 0.54) & (blue > 0.38) & (red > blue * 0.93))
    blossom &= ~branch
    ground = colour(source[sky].mean(0))
    # Inpaint only for sampling a smooth uninterrupted turquoise underpainting.
    inpainted = cv2.inpaint((source * 255).astype(np.uint8), (~sky).astype(np.uint8) * 255, 7, cv2.INPAINT_TELEA).astype(np.float32) / 255
    smooth = gaussian_filter(inpainted, sigma=(13, 13, 0))
    rng = np.random.default_rng(1890)
    sky_strokes = []
    rows, columns = 38, 10
    for row in range(rows):
        y = (row + 0.5) * h / rows
        for column in range(columns):
            x0 = column * w / columns - rng.uniform(0, 18)
            x1 = min(w, (column + 1.15) * w / columns)
            midx = int(np.clip((x0 + x1) / 2, 0, w - 1))
            midy = int(np.clip(y, 0, h - 1))
            c = colour(smooth[midy, midx] * 0.45 + np.array(list(rgb(ground))) * 0.55)
            sky_strokes.append({"p": [round(x0, 1), round(y, 1), round(x1, 1), round(y + rng.uniform(-2, 2), 1)], "c": c, "s": 24, "o": 1.0, "stage": "blocking"})
    branch_regions = colour_regions(branch, source, 10)
    candidates = [stripes(region, pid, min(8.0, max(2.5, math.sqrt(region["area"]) * 0.38))) for region in branch_regions]
    branch_strokes = allocate(candidates, branch_regions, 500, "edges")
    for stroke in branch_strokes:
        stroke.pop("weight", None)
        stroke["stage"] = "form"
    curved = skeleton_paths(branch, source, 180)
    # Complete the structural budget with the longest remaining mask-clipped marks.
    if len(curved) < 180:
        curved += branch_strokes[:180 - len(curved)]
        for stroke in curved:
            stroke["stage"] = "refinement"
    blossom_regions = components(cv2.morphologyEx(blossom.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)), source, 5)
    blossom_regions = [r for r in blossom_regions if r["luminance"] > 0.43]
    blossom_sets = [stripes(region, pid, min(8.5, max(2.2, math.sqrt(region["area"]) * 0.50))) for region in blossom_regions]
    blossom_strokes = allocate(blossom_sets, blossom_regions, 240, "edges") if blossom_regions else []
    for stroke in blossom_strokes:
        stroke.pop("weight", None)
        stroke["stage"] = "detail"
        stroke["s"] = min(stroke["s"], 7.5)
    blossom_strokes.sort(key=lambda s: rgb(s["c"]).mean())
    stages = [
        {"id": "blocking", "label": "Turquoise sky", "strokes": sky_strokes},
        {"id": "form", "label": "Branch colour", "strokes": branch_strokes},
        {"id": "refinement", "label": "Curving branches", "strokes": curved[:180]},
        {"id": "detail", "label": "White-pink blossoms", "strokes": blossom_strokes},
    ]
    return {"id": pid, "title": title, "artist": artist, "year": year, "description": description, "width": w, "height": h, "ground": ground, "reference": f"../references/{pid}.jpg", "seed": 1890, "profile": "almond-layers", "planner": "Inpainted smooth sky; colour-segmented branch masks; curved skeleton-following branch strokes; white-pink blossom dabs", "credit": {"author": artist, "licence": "Public domain", "source": "Wikimedia Commons", "url": URLS[pid]}, "strokeCount": sum(len(stage["strokes"]) for stage in stages), "stages": stages}


if __name__ == "__main__":
    recipe = plan()
    path = ROOT / "recipes" / "almond-blossom.json"
    path.write_text(json.dumps(recipe, separators=(",", ":")) + "\n")
    print(f"Planned Almond Blossom: {recipe['strokeCount']} strokes; stages {[len(s['strokes']) for s in recipe['stages']]}")
