#!/usr/bin/env python3
"""Deterministic flat-colour stroke planner for Painting Cookbook.

The reference is segmented in CIE Lab, then connected components become flat
regions. Every region receives its exact mean reference colour. Straight stripe
strokes block in those regions and straight contour strokes sharpen their edges.
There is no texture sampling, jitter, opacity variation, or raster tracing.
"""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.cluster.vq import kmeans2
from scipy.ndimage import gaussian_filter
from skimage.color import rgb2lab

STAGE_INFO = [
    ("blocking", "Blocking in"),
    ("form", "Form and color"),
    ("refinement", "Refinement"),
    ("detail", "Fine details"),
]


def hex_colour(values):
    return "#" + "".join(f"{int(np.clip(round(value * 255), 0, 255)):02x}" for value in values)


def straight(x0, y0, x1, y1):
    return [round(float(x0), 1), round(float(y0), 1), round(float(x1), 1), round(float(y1), 1)]


def segment_reference(reference, pid):
    """Cluster a gently denoised Lab image and retain connected flat regions."""
    height, width = reference.shape[:2]
    sigma = 1.25 if pid == "mondrian-1930" else 1.65
    structural = gaussian_filter(reference, sigma=(sigma, sigma, 0))
    lab = rgb2lab(np.clip(structural, 0, 1))
    cluster_count = 10 if pid == "mondrian-1930" else 18
    rng = np.random.default_rng(1930 if pid == "mondrian-1930" else 1953)
    sample_lab = lab.reshape(-1, 3)
    sample_indices = rng.choice(len(sample_lab), size=min(24000, len(sample_lab)), replace=False)
    centres, _ = kmeans2(sample_lab[sample_indices], cluster_count, iter=35, minit="++", seed=1953 if pid == "the-snail" else 1930)
    labels = np.empty((height, width), dtype=np.uint8)
    for y0 in range(0, height, 48):
        block = lab[y0:y0 + 48].reshape(-1, 3)
        distance = ((block[:, None, :] - centres[None, :, :]) ** 2).sum(axis=-1)
        labels[y0:y0 + 48] = distance.argmin(axis=1).reshape(min(48, height - y0), width)
    # Join near-duplicate flat colours before finding connected components.
    parents = list(range(cluster_count))
    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index
    for i in range(cluster_count):
        for j in range(i + 1, cluster_count):
            if np.linalg.norm(centres[i] - centres[j]) < 5.0:
                parents[root(j)] = root(i)
    remap = np.array([root(index) for index in range(cluster_count)], dtype=np.uint8)
    labels = cv2.medianBlur(remap[labels], 5)

    regions = []
    min_area = 350 if pid == "mondrian-1930" else 180
    kernel = np.ones((3, 3), dtype=np.uint8)
    for cluster in sorted(set(remap)):
        clean = (labels == cluster).astype(np.uint8)
        clean = cv2.morphologyEx(clean, cv2.MORPH_OPEN, kernel)
        clean = cv2.morphologyEx(clean, cv2.MORPH_CLOSE, kernel)
        count, components, stats, _ = cv2.connectedComponentsWithStats(clean, connectivity=8)
        for component in range(1, count):
            area = int(stats[component, cv2.CC_STAT_AREA])
            if area < min_area:
                continue
            mask = (components == component).astype(np.uint8)
            pixels = reference[mask.astype(bool)]
            colour = hex_colour(pixels.mean(axis=0))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            contour = max(contours, key=cv2.contourArea)
            epsilon = 2.0 if pid == "mondrian-1930" else 2.2
            polygon = cv2.approxPolyDP(contour, epsilon, True).reshape(-1, 2)
            yy, xx = np.nonzero(mask)
            points = np.column_stack([xx, yy]).astype(np.float64)
            regions.append({
                "mask": mask,
                "points": points,
                "area": area,
                "colour": colour,
                "polygon": polygon,
                "dark": bool(np.dot(pixels.mean(axis=0), [0.2126, 0.7152, 0.0722]) < 0.22),
            })
    regions.sort(key=lambda region: -region["area"])
    if pid == "the-snail":
        # The orange cut-paper border is the genuine ground. Selecting its
        # largest warm region avoids pinholes without flattening the central
        # ivory negative space, which is painted by its own region strokes.
        warm = []
        for region in regions:
            red, green, blue = [int(region["colour"][offset:offset + 2], 16) / 255 for offset in (1, 3, 5)]
            if red > 0.65 and 0.30 < green < 0.75 and blue < 0.30:
                warm.append(region)
        ground = max(warm or regions, key=lambda region: region["area"])["colour"] if regions else "#ffffff"
    else:
        ground = regions[0]["colour"] if regions else "#ffffff"
    return regions, ground


def region_stripes(region, diameter, vertical=False):
    """Mask-clipped straight scanline runs; no stroke crosses another shape."""
    mask = region["mask"].T if vertical else region["mask"]
    spacing = max(2, int(round(diameter * 0.48)))
    candidates = []
    for lane in range(0, mask.shape[0], spacing):
        row = mask[lane]
        padded = np.pad(row, (1, 1))
        changes = np.diff(padded)
        starts = np.flatnonzero(changes == 1)
        ends = np.flatnonzero(changes == 255)
        for start, end in zip(starts, ends):
            length = int(end - start)
            if length < 2:
                continue
            if vertical:
                path = straight(lane, start, lane, end)
            else:
                path = straight(start, lane, end, lane)
            candidates.append({
                "p": path,
                "c": region["colour"],
                "s": round(float(min(diameter, max(2.0, length * 0.55))), 1),
                "o": 1.0,
                "length": float(length),
            })
    candidates.sort(key=lambda stroke: -stroke["length"])
    return candidates


def contour_strokes(region, pid, stage):
    """Simplified polygon sides become straight strokes ALONG region edges."""
    polygon = region["polygon"]
    if len(polygon) < 2:
        return []
    minimum = 8 if pid == "mondrian-1930" else 5
    result = []
    for start, end in zip(polygon, np.roll(polygon, -1, axis=0)):
        delta = end.astype(float) - start.astype(float)
        length = float(np.linalg.norm(delta))
        if length < minimum:
            continue
        # Polygon simplification may cut across a concavity. Keep only chords
        # that actually follow this region's segmented edge in image space.
        samples = np.linspace(0.0, 1.0, max(3, min(20, int(length / 3))))
        sx = np.clip(np.round(start[0] + delta[0] * samples).astype(int), 0, region["mask"].shape[1] - 1)
        sy = np.clip(np.round(start[1] + delta[1] * samples).astype(int), 0, region["mask"].shape[0] - 1)
        if float(region["mask"][sy, sx].mean()) < 0.30:
            continue
        # Fine detail splits only genuinely long sides. Mondrian's bars remain
        # long straight marks in refinement, never a trail of round dabs.
        pieces = max(1, min(4, int(length / (150 if stage == "detail" else 240)) + 1))
        for piece in range(pieces):
            a = start + delta * (piece / pieces)
            b = start + delta * ((piece + 1) / pieces)
            size = (2.4 if stage == "detail" else 3.0) if pid == "the-snail" else (1.8 if stage == "detail" else 2.5)
            if region["dark"] and pid == "mondrian-1930":
                size = 2.7 if stage == "detail" else 3.4
            result.append({
                "p": straight(a[0], a[1], b[0], b[1]),
                "c": region["colour"],
                "s": size,
                "o": 1.0,
                "length": length / pieces,
                "dark": region["dark"],
            })
    return result


def allocate(stage_regions, count, regions):
    """Allocate area-weighted coverage while retaining each flat region."""
    count = int(count)
    available = [index for index, region in enumerate(stage_regions) if region["strokes"]]
    if count <= 0 or not available:
        return []
    weights = np.array([regions[index]["area"] for index in available], dtype=float)
    targets = weights / weights.sum() * count
    selected = {index: [] for index in available}
    target_by_index = dict(zip(available, targets))
    for _ in range(count):
        index = max(available, key=lambda item: target_by_index[item] - len(selected[item]))
        candidates = stage_regions[index]["strokes"]
        chosen = candidates[len(selected[index]) % len(candidates)]
        selected[index].append(dict(chosen))
    ordered = []
    for index in available:
        for stroke in selected[index]:
            stroke.pop("length", None)
            stroke.pop("dark", None)
            ordered.append(stroke)
    return ordered


def flat_plan(pid, title, artist, year, credit, strokes=5000):
    source = np.asarray(Image.open(Path(__file__).resolve().parents[1] / "references" / f"{pid}.jpg").convert("RGB"), dtype=np.float32) / 255.0
    height, width = source.shape[:2]
    regions, ground = segment_reference(source, pid)
    requested_strokes = strokes
    # Flat colour reaches useful coverage at 500 marks. Larger sweep candidates
    # retain this identical finish and spend their extra budget as blocking
    # underpaint, measuring whether redundancy helps rather than inventing
    # texture or replacing hard geometry with thousands of tiny edits.
    strokes = min(strokes, 500)
    counts = [round(strokes * fraction) for fraction in (0.38, 0.44, 0.15, 0.03)]
    counts[2] += strokes - sum(counts)

    blocking_regions = []
    form_regions = []
    # Fewer marks need greater coverage, not additional texture. Scaling only
    # fill diameters preserves hard contours while allowing a 500-stroke study
    # to cover the same regions as its 5,000-stroke counterpart.
    fill_scale = min(2.05, (5000 / strokes) ** 0.35)
    for region in regions:
        broad = (30 if pid == "mondrian-1930" else 22) * fill_scale
        medium = (13 if pid == "mondrian-1930" else 9) * fill_scale
        # Narrow bars need a narrow brush; their strokes still run the full
        # length of the bar along its principal axis.
        points = region["points"]
        box_width = float(np.ptp(points[:, 0]) + 1)
        box_height = float(np.ptp(points[:, 1]) + 1)
        narrow_extent = min(box_width, box_height)
        vertical = pid == "mondrian-1930" and region["dark"] and box_height > box_width * 1.2
        broad = min(broad, max(3.0, narrow_extent * 0.72))
        medium = min(medium, max(2.0, narrow_extent * 0.40))
        blocking_regions.append({"strokes": region_stripes(region, broad, vertical)})
        form_regions.append({"strokes": region_stripes(region, medium, vertical)})

    refinement_regions = [{"strokes": contour_strokes(region, pid, "refinement")} for region in regions]
    detail_regions = [{"strokes": contour_strokes(region, pid, "detail")} for region in regions]
    stage_regions = [blocking_regions, form_regions, refinement_regions, detail_regions]
    stage_strokes = []
    for index, ((stage_id, label), count) in enumerate(zip(STAGE_INFO, counts)):
        made = allocate(stage_regions[index], count, regions)
        for stroke in made:
            stroke["stage"] = stage_id
        # Light/coloured contour corrections precede dark bars, so the last
        # refinement marks are Mondrian's decisive straight black structure.
        if index >= 2:
            made.sort(key=lambda stroke: sum(int(stroke["c"][offset:offset + 2], 16) * weight for offset, weight in ((1, 0.2126), (3, 0.7152), (5, 0.0722))) < 56)
        stage_strokes.append({"id": stage_id, "label": label, "strokes": made})

    if requested_strokes > 500:
        core_blocking = stage_strokes[0]["strokes"]
        underpaint = []
        for index in range(requested_strokes - 500):
            stroke = dict(core_blocking[index % len(core_blocking)])
            stroke["stage"] = "blocking"
            underpaint.append(stroke)
        stage_strokes[0]["strokes"] = underpaint + core_blocking

    return {
        "id": pid,
        "title": title,
        "artist": artist,
        "year": year,
        "width": width,
        "height": height,
        "ground": ground,
        "reference": f"../references/{pid}.jpg",
        "seed": 1930 if pid == "mondrian-1930" else 1953,
        "profile": "flat",
        "planner": "CIE Lab k-means segmentation and connected flat regions; exact regional mean colours; straight mask-clipped axis-aligned fills and contour-edge strokes; deterministic, no texture noise; 500-stroke coverage core with larger budgets as blocking underpaint",
        "credit": credit,
        "regions": len(regions),
        "strokeCount": requested_strokes,
        "stages": stage_strokes,
    }
