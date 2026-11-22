#!/usr/bin/env python3
"""Rebuild cut-paper works as flat polygons filled with straight brush strokes.

The Snail uses Lab k-means connected components, a three-pixel polygon
simplification, principal-axis scan-line fills inside eroded polygons, and
small exact-colour strokes along every inset edge. No texture or translucent
paint is used. The same region helpers are reused by the Mondrian repair.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.cluster.vq import kmeans2
from scipy.ndimage import gaussian_filter
from skimage.color import rgb2lab
from skimage.measure import approximate_polygon, find_contours

ROOT = Path(__file__).resolve().parents[1]
STAGES = [
    ("blocking", "Blocking in", "Lay down the orange ground and the flat white sheet."),
    ("form", "Form and color", "Fill each cut-paper piece with straight, opaque strokes."),
    ("refinement", "Refinement", "Sharpen every straight edge without rounding the corners."),
    ("detail", "Fine details", "Restore the small coloured pieces and the black square."),
]


def hex_colour(values):
    return "#" + "".join(f"{int(np.clip(round(v), 0, 255)):02x}" for v in values)


def straight(a, b):
    return [round(float(a[0]), 2), round(float(a[1]), 2), round(float(b[0]), 2), round(float(b[1]), 2)]


def polygon_for_mask(mask):
    """Return the largest external component contour as an approximate polygon."""
    padded = np.pad(mask.astype(np.uint8), 1)
    contours = find_contours(padded, 0.5)
    if not contours:
        return None
    contour = max(contours, key=lambda item: cv2.contourArea((item[:, ::-1] - 1).astype(np.float32)))
    polygon = approximate_polygon(contour, tolerance=3.0)
    xy = polygon[:, ::-1] - 1.0
    if len(xy) > 1 and np.allclose(xy[0], xy[-1]):
        xy = xy[:-1]
    if len(xy) < 3 or abs(cv2.contourArea(xy.astype(np.float32))) < 20:
        return None
    return xy


def polygon_mask(polygon, width, height):
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(mask, [np.rint(polygon).astype(np.int32)], 1)
    return mask


def principal_axes(polygon):
    centre = polygon.mean(axis=0)
    _, _, vt = np.linalg.svd(polygon - centre, full_matrices=False)
    u = vt[0]
    # Stable orientation makes output deterministic across SVD implementations.
    if u[0] < 0 or (abs(u[0]) < 1e-9 and u[1] < 0):
        u = -u
    u /= np.linalg.norm(u)
    v = np.array([-u[1], u[0]])
    return u, v


def scan_strokes(polygon, colour, diameter, stage):
    """Fill a polygon with straight runs whose centres stay a radius inside it."""
    height, width = 970, 960
    base = polygon_mask(polygon, width, height)
    inset = max(1, int(round(diameter * 0.48)))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (inset * 2 + 1, inset * 2 + 1))
    safe = cv2.erode(base, kernel)
    if not safe.any():
        safe = base
    u, v = principal_axes(polygon)
    projections_u = polygon @ u
    projections_v = polygon @ v
    min_u, max_u = float(projections_u.min()), float(projections_u.max())
    min_v, max_v = float(projections_v.min()), float(projections_v.max())
    out_w = max(2, int(np.ceil(max_u - min_u)) + 3)
    out_h = max(2, int(np.ceil(max_v - min_v)) + 3)
    matrix = np.array([[u[0], u[1], -min_u + 1], [v[0], v[1], -min_v + 1]], dtype=np.float64)
    rotated = cv2.warpAffine(safe, matrix, (out_w, out_h), flags=cv2.INTER_NEAREST)
    spacing = max(2, int(round(diameter * 0.31)))
    strokes = []
    # Two interleaved sets of true scan lines ensure flat opaque coverage.
    for pass_index in range(2):
        for lane in range(1 + pass_index * spacing // 2, out_h - 1, spacing):
            row = rotated[lane]
            changes = np.diff(np.pad(row, (1, 1)))
            starts = np.flatnonzero(changes == 1)
            ends = np.flatnonzero(changes == 255)
            for start, end in zip(starts, ends):
                if end - start < 2:
                    continue
                # Trim one pixel so the soft stamp does not cross the inset mask.
                a_u, b_u = start + min_u, end - 1 + min_u
                line_v = lane + min_v - 1
                a = a_u * u + line_v * v
                b = b_u * u + line_v * v
                strokes.append({"p": straight(a, b), "c": colour, "s": round(float(diameter), 2), "o": 1.0, "stage": stage})
    return strokes


def edge_strokes(polygon, colour, diameter, stage, second=False):
    """Place one straight stroke just inside each simplified polygon edge."""
    if len(polygon) < 3:
        return []
    height, width = 970, 960
    base = polygon_mask(polygon, width, height)
    result = []
    offset = diameter * (0.47 if not second else 0.82)
    for a, b in zip(polygon, np.roll(polygon, -1, axis=0)):
        delta = b - a
        length = float(np.linalg.norm(delta))
        if length < 5:
            continue
        tangent = delta / length
        normals = [np.array([-tangent[1], tangent[0]]), np.array([tangent[1], -tangent[0]])]
        midpoint = (a + b) / 2
        inward = None
        for normal in normals:
            probe = midpoint + normal * max(2, offset)
            x, y = np.rint(probe).astype(int)
            if 0 <= x < width and 0 <= y < height and base[y, x]:
                inward = normal
                break
        if inward is None:
            inward = normals[0]
        # Move whole edges inward, preserving straight lines and sharp joins.
        aa = a + inward * offset
        bb = b + inward * offset
        # Avoid overshoot at very sharp convex corners.
        trim = min(length * 0.08, offset * 0.35)
        aa = aa + tangent * trim
        bb = bb - tangent * trim
        result.append({"p": straight(aa, bb), "c": colour, "s": round(float(diameter), 2), "o": 1.0, "stage": stage})
    return result


def segment_snail(reference):
    """Segment into fourteen Lab colours and retain useful connected pieces."""
    height, width = reference.shape[:2]
    structural = gaussian_filter(reference, sigma=(0.65, 0.65, 0))
    lab = rgb2lab(np.clip(structural, 0, 1))
    rng = np.random.default_rng(1953)
    samples = lab.reshape(-1, 3)
    indices = rng.choice(len(samples), size=30000, replace=False)
    centres, _ = kmeans2(samples[indices], 14, iter=45, minit="++", seed=1953)
    labels = np.empty((height, width), dtype=np.uint8)
    for y0 in range(0, height, 64):
        block = lab[y0:y0 + 64].reshape(-1, 3)
        distances = ((block[:, None, :] - centres[None, :, :]) ** 2).sum(axis=-1)
        labels[y0:y0 + 64] = distances.argmin(axis=1).reshape(min(64, height - y0), width)
    labels = cv2.medianBlur(labels, 3)

    border = np.concatenate([reference[:12].reshape(-1, 3), reference[-12:].reshape(-1, 3), reference[:, :12].reshape(-1, 3), reference[:, -12:].reshape(-1, 3)])
    ground_rgb = np.median(border, axis=0) * 255
    regions = []
    for cluster in range(14):
        binary = (labels == cluster).astype(np.uint8)
        count, components, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        for component in range(1, count):
            area = int(stats[component, cv2.CC_STAT_AREA])
            # Cut-paper works have no meaningful sub-1,200-pixel pieces here.
            # Dropping tiny antialias clusters prevents dark fringe components
            # from being painted last as halos around the orange cutouts.
            if area < 1200:
                continue
            component_mask = (components == component).astype(np.uint8)
            polygon = polygon_for_mask(component_mask)
            if polygon is None:
                continue
            pixels = reference[component_mask.astype(bool)] * 255
            median = np.median(pixels, axis=0)
            yy, xx = np.nonzero(component_mask)
            touches_border = bool(component_mask[0].any() or component_mask[-1].any() or component_mask[:, 0].any() or component_mask[:, -1].any())
            regions.append({
                "area": area,
                "polygon": polygon,
                "colour": hex_colour(median),
                "rgb": median,
                "centroid": np.array([xx.mean(), yy.mean()]),
                "ground_like": bool(np.linalg.norm(median - ground_rgb) < 45 and touches_border),
            })

    # The ivory paper is one underlying sheet, not several white components.
    # Recover its outer silhouette from everything inside the orange surround;
    # orange shapes within it are holes which are repainted in a later pass.
    ground_distance = np.linalg.norm(reference * 255 - ground_rgb, axis=-1)
    non_ground = (ground_distance >= 45).astype(np.uint8)
    non_ground = cv2.morphologyEx(non_ground, cv2.MORPH_CLOSE, np.ones((3, 3), dtype=np.uint8))
    count, components, stats, _ = cv2.connectedComponentsWithStats(non_ground, connectivity=8)
    central_candidates = []
    for component in range(1, count):
        mask = components == component
        if mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any():
            continue
        central_candidates.append((int(stats[component, cv2.CC_STAT_AREA]), component))
    if not central_candidates:
        raise RuntimeError("No central paper sheet found")
    paper_area, paper_component = max(central_candidates)
    paper_mask = (components == paper_component).astype(np.uint8)
    paper_polygon = polygon_for_mask(paper_mask)
    if paper_polygon is None:
        raise RuntimeError("No paper-sheet polygon found")
    light_pixels = reference[(paper_mask.astype(bool)) & (reference.min(axis=-1) > 0.58) & (np.ptp(reference, axis=-1) < 0.40)] * 255
    paper_rgb = np.median(light_pixels, axis=0)
    yy, xx = np.nonzero(paper_mask)
    paper = {"area": paper_area, "polygon": paper_polygon, "colour": hex_colour(paper_rgb), "rgb": paper_rgb, "centroid": np.array([xx.mean(), yy.mean()])}

    # White negative-space components now belong to the sheet. Keep only the
    # genuinely coloured cutouts, including orange shapes that do not touch
    # the outer orange ground.
    pieces = [r for r in regions if not r["ground_like"] and not (r["rgb"].min() > 135 and np.ptp(r["rgb"]) < 105)]
    pieces.sort(key=lambda r: -r["area"])
    return hex_colour(ground_rgb), paper, pieces


def snail_plan(output=None, target=2000):
    reference_path = ROOT / "references" / "the-snail.jpg"
    reference = np.asarray(Image.open(reference_path).convert("RGB"), dtype=np.float32) / 255.0
    height, width = reference.shape[:2]
    ground, paper, pieces = segment_snail(reference)
    ground_polygon = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=float)

    all_regions = [paper] + pieces
    blocking = scan_strokes(ground_polygon, ground, 40, "blocking")
    form = []
    refinement = []
    detail = []
    for order, region in enumerate(all_regions):
        polygon = region["polygon"]
        u, v = principal_axes(polygon)
        short_side = float(np.ptp(polygon @ v))
        diameter = min(40.0, max(5.0, short_side * 0.5))
        stage = "blocking" if region is paper else ("detail" if region["area"] < 1800 else "form")
        fills = scan_strokes(polygon, region["colour"], diameter, stage)
        (blocking if region is paper else form if stage == "form" else detail).extend(fills)
        edge_size = min(8.0, max(5.0, diameter * 0.30))
        refinement.extend(edge_strokes(polygon, region["colour"], edge_size, stage))

    # Use the requested budget for denser coverage and a second inset edge pass,
    # never for noise. Keep region paint order intact: ground, sheet, pieces.
    groups = [blocking, form, refinement, detail]
    total = sum(map(len, groups))
    if total < target:
        supplements = []
        for region in all_regions:
            polygon = region["polygon"]
            u, v = principal_axes(polygon)
            short_side = float(np.ptp(polygon @ v))
            diameter = min(40.0, max(5.0, short_side * 0.5))
            edge_size = min(8.0, max(5.0, diameter * 0.30))
            supplements.extend(edge_strokes(polygon, region["colour"], edge_size, "refinement", second=True))
        refinement.extend(supplements[:target - total])
        total = sum(map(len, groups))
    if total > target:
        # First remove duplicate scan passes evenly from the end of each fill
        # group; all one-per-edge sharpening strokes are preserved.
        overflow = total - target
        for group in (detail, form, blocking):
            if overflow <= 0:
                break
            removable = max(0, len(group) - 1)
            take = min(overflow, removable)
            if take:
                del group[-take:]
                overflow -= take
        if overflow:
            del refinement[-overflow:]
    total = sum(map(len, groups))
    # Exact-count top-up repeats useful central straight fills, not new marks
    # with arbitrary colours or positions.
    if total < target:
        source = form or blocking
        index = 0
        while total < target:
            mark = dict(source[index % len(source)])
            mark["p"] = list(mark["p"])
            form.append(mark)
            total += 1
            index += 1

    recipe = {
        "id": "the-snail",
        "title": "The Snail",
        "artist": "Henri Matisse",
        "year": "1953",
        "width": width,
        "height": height,
        "ground": ground,
        "reference": "../references/the-snail.jpg",
        "seed": 1953,
        "profile": "flat",
        "planner": "14-colour CIE Lab k-means; connected components; median flat colours; skimage contours and approximate_polygon tolerance 3 px; principal-axis straight fills inside brush-radius-eroded polygons; 5–8 px exact-colour inset edge strokes; orange ground, white sheet, then coloured pieces largest to smallest; opacity 1 and no texture noise",
        "credit": {"author": "Tate, London", "licence": "Public domain in the EU", "note": "Public domain in the EU; in copyright in some other countries.", "source": "Tate", "url": "https://www.tate.org.uk/art/artworks/matisse-the-snail-t00540"},
        "description": "Matisse's cut-paper spiral rebuilt as discrete flat pieces: an orange ground, a straight-edged ivory sheet, coloured polygon fills and crisp inset edges, ending with the small shapes and black square.",
        "regions": len(all_regions),
        "strokeCount": total,
        "stages": [],
    }
    stage_groups = [blocking, form, refinement, detail]
    for (stage_id, label, tip), strokes in zip(STAGES, stage_groups):
        recipe["stages"].append({"id": stage_id, "label": label, "tip": tip, "strokes": strokes})
    assert recipe["strokeCount"] == target
    assert all(stroke["o"] == 1 for stage in recipe["stages"] for stroke in stage["strokes"])
    assert all(len(stroke["p"]) == 4 for stage in recipe["stages"] for stroke in stage["strokes"])
    destination = output or ROOT / "recipes" / "the-snail.json"
    destination.write_text(json.dumps(recipe, separators=(",", ":")) + "\n")
    debug = {
        "ground": ground,
        "paper": {"area": paper["area"], "colour": paper["colour"], "vertices": len(paper["polygon"])},
        "pieces": [{"area": r["area"], "colour": r["colour"], "vertices": len(r["polygon"]), "centroid": np.round(r["centroid"], 1).tolist()} for r in pieces],
        "stageCounts": [len(stage["strokes"]) for stage in recipe["stages"]],
        "strokes": total,
    }
    print(json.dumps(debug, indent=2))
    return recipe


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("painting", choices=["the-snail"])
    parser.add_argument("--strokes", type=int, default=2000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    snail_plan(args.output, args.strokes)


if __name__ == "__main__":
    main()
