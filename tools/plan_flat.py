#!/usr/bin/env python3
"""Deterministic flat-colour stroke planner for Painting Cookbook.

The reference is segmented in CIE Lab, then connected components become flat
regions. Every region receives its exact mean reference colour. Straight stripe
strokes block in those regions and straight contour strokes sharpen their edges.
There is no texture sampling, jitter, opacity variation, or raster tracing.
"""
import math

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
    cluster_count = 14 if pid == "mondrian-1930" else 20
    rng = np.random.default_rng(1930 if pid == "mondrian-1930" else 1953)
    sample_lab = lab.reshape(-1, 3)
    sample_indices = rng.choice(len(sample_lab), size=min(24000, len(sample_lab)), replace=False)
    centres, _ = kmeans2(sample_lab[sample_indices], cluster_count, iter=35, minit="++", seed=1953 if pid == "the-snail" else 1930)
    labels = np.empty((height, width), dtype=np.uint8)
    for y0 in range(0, height, 48):
        block = lab[y0:y0 + 48].reshape(-1, 3)
        distance = ((block[:, None, :] - centres[None, :, :]) ** 2).sum(axis=-1)
        labels[y0:y0 + 48] = distance.argmin(axis=1).reshape(block.shape[0] and min(48, height - y0), width)
    labels = cv2.medianBlur(labels, 3)

    regions = []
    min_area = 100 if pid == "mondrian-1930" else 90
    for cluster in range(cluster_count):
        count, components, stats, _ = cv2.connectedComponentsWithStats((labels == cluster).astype(np.uint8), connectivity=8)
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
            epsilon = 1.35 if pid == "mondrian-1930" else 1.75
            polygon = cv2.approxPolyDP(contour, epsilon, True).reshape(-1, 2)
            yy, xx = np.nonzero(mask)
            points = np.column_stack([xx, yy]).astype(np.float64)
            centre = points.mean(axis=0)
            covariance = np.cov((points - centre).T) if len(points) > 2 else np.eye(2)
            eigenvalues, eigenvectors = np.linalg.eigh(covariance)
            tangent = eigenvectors[:, int(np.argmax(eigenvalues))]
            # Image-space signs are irrelevant for a two-ended stroke. Keeping
            # x positive makes all output deterministic and easy to inspect.
            if tangent[0] < 0:
                tangent = -tangent
            regions.append({
                "mask": mask,
                "points": points,
                "centre": centre,
                "tangent": tangent,
                "area": area,
                "colour": colour,
                "polygon": polygon,
                "dark": bool(np.dot(pixels.mean(axis=0), [0.2126, 0.7152, 0.0722]) < 0.22),
            })
    regions.sort(key=lambda region: -region["area"])
    ground = regions[0]["colour"] if regions else "#ffffff"
    return regions, ground


def region_stripes(region, diameter):
    """Long PCA-aligned straight stripes clipped to each region's extents."""
    points = region["points"]
    centre = region["centre"]
    tangent = region["tangent"]
    normal = np.array([-tangent[1], tangent[0]])
    relative = points - centre
    along = relative @ tangent
    across = relative @ normal
    spacing = max(2.0, diameter * 0.62)
    candidates = []
    low = math.floor(float(across.min()) / spacing) * spacing
    high = float(across.max())
    lane = low
    while lane <= high + spacing:
        selected = np.abs(across - lane) <= spacing * 0.47
        if int(selected.sum()) >= 2:
            values = along[selected]
            length = float(values.max() - values.min())
            if length >= max(2.0, diameter * 0.18):
                mid_along = (float(values.min()) + float(values.max())) / 2
                mid_across = float(np.median(across[selected]))
                midpoint = centre + tangent * mid_along + normal * mid_across
                half = tangent * (length / 2)
                p0, p1 = midpoint - half, midpoint + half
                candidates.append({
                    "p": straight(p0[0], p0[1], p1[0], p1[1]),
                    "c": region["colour"],
                    "s": round(float(diameter), 1),
                    "o": 1.0,
                    "length": length,
                })
        lane += spacing
    # Cover long, central runs first; subsequent cycles finish the silhouette.
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


def allocate(strokes, count, regions):
    """Give every region a turn before repeating its useful straight marks."""
    count = int(count)
    if count <= 0:
        return []
    per_region = [region["strokes"] for region in regions if region["strokes"]]
    if not per_region:
        return []
    ordered = []
    for cycle in range(max(len(candidates) for candidates in per_region)):
        for candidates in per_region:
            if cycle < len(candidates):
                stroke = dict(candidates[cycle])
                ordered.append(stroke)
    if not ordered:
        return []
    selected = [dict(stroke) for stroke in ordered[:count]]
    if len(selected) < count:
        # Repeated opaque strokes consolidate soft-brush falloff, not texture.
        for index in range(count - len(selected)):
            selected.append(dict(ordered[index % len(ordered)]))
    for stroke in selected:
        stroke.pop("length", None)
        stroke.pop("dark", None)
    return selected[:count]


def flat_plan(pid, title, artist, year, credit, strokes=5000):
    source = np.asarray(Image.open(__import__("pathlib").Path(__file__).resolve().parents[1] / "references" / f"{pid}.jpg").convert("RGB"), dtype=np.float32) / 255.0
    height, width = source.shape[:2]
    regions, ground = segment_reference(source, pid)
    counts = [round(strokes * fraction) for fraction in (0.34, 0.40, 0.20, 0.06)]
    counts[2] += strokes - sum(counts)

    blocking_regions = []
    form_regions = []
    for region in regions:
        broad = 30 if pid == "mondrian-1930" else 22
        medium = 13 if pid == "mondrian-1930" else 9
        # Narrow bars need a narrow brush; their strokes still run the full
        # length of the bar along its principal axis.
        extent = np.ptp((region["points"] - region["centre"]) @ np.array([-region["tangent"][1], region["tangent"][0]]))
        broad = min(broad, max(3.0, extent * 0.72))
        medium = min(medium, max(2.0, extent * 0.40))
        blocking_regions.append({"strokes": region_stripes(region, broad)})
        form_regions.append({"strokes": region_stripes(region, medium)})

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
            made.sort(key=lambda stroke: stroke["c"] == "#000000")
        stage_strokes.append({"id": stage_id, "label": label, "strokes": made})

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
        "planner": "CIE Lab k-means segmentation and connected flat regions; exact regional mean colours; straight PCA-aligned stripe fills and straight contour-edge strokes; deterministic, no texture noise",
        "credit": credit,
        "regions": len(regions),
        "strokeCount": strokes,
        "stages": stage_strokes,
    }
