#!/usr/bin/env python3
"""Multiscale, grid-free stroke discovery for Painting Cookbook.

The reference is analysed, never traced as pixels into a render. Each stage paints
curved paths sampled from progressively less blurred colour fields. Structure
tensor tangents and painting-specific flow fields orient the marks. An optional
refinement pass distributes fine strokes according to actual raster residuals.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates, sobel

ROOT = Path(__file__).resolve().parents[1]
META = {
    "mona-lisa": ("Mona Lisa", "Leonardo da Vinci", "c. 1503–1519"),
    "girl-with-a-pearl-earring": ("Girl with a Pearl Earring", "Johannes Vermeer", "c. 1665"),
    "starry-night": ("The Starry Night", "Vincent van Gogh", "1889"),
    "great-wave": ("The Great Wave off Kanagawa", "Katsushika Hokusai", "c. 1830–1832"),
    "van-gogh-self-portrait": ("Self-Portrait", "Vincent van Gogh", "1887"),
    "countach": ("Lamborghini Countach LP5000 S", "Photo: Palauenc05", "1983"),
    "breakfast-at-tiffanys": ("Audrey Hepburn, Breakfast at Tiffany's", "Paramount publicity photo", "1961"),
    "marilyn-1953": ("Marilyn Monroe", "Studio publicity still (Photoplay)", "1953"),
    "the-scream": ("The Scream", "Edvard Munch", "1893"),
    "blue-marble": ("The Blue Marble", "Photo: NASA, Apollo 17 crew", "1972"),
    "sunflowers": ("Sunflowers", "Vincent van Gogh", "1888"),
    "the-snail": ("The Snail", "Henri Matisse", "1953"),
    "mondrian-1930": ("Composition with Red, Blue and Yellow", "Piet Mondrian", "1930"),
}
CREDITS = {
    "countach": {"author": "Palauenc05", "licence": "CC BY-SA 4.0", "url": "https://commons.wikimedia.org/wiki/File:Lamborghini_Countach_LP_5000S_1983.jpg"},
    "breakfast-at-tiffanys": {"author": "Paramount publicity photo", "licence": "Public domain", "url": "https://commons.wikimedia.org/wiki/File:Audrey_Hepburn_in_Breakfast_at_Tiffanys_3.jpg"},
    "marilyn-1953": {"author": "Studio publicity still (Photoplay)", "licence": "Public domain", "url": "https://commons.wikimedia.org/wiki/File:Marilyn_Monroe,_Photoplay_1953_(cropped).jpg"},
    "the-scream": {"author": "Edvard Munch", "licence": "Public domain", "url": "https://commons.wikimedia.org/wiki/File:Edvard_Munch,_1893,_The_Scream,_oil,_tempera_and_pastel_on_cardboard,_91_x_73_cm,_National_Gallery_of_Norway.jpg"},
    "blue-marble": {"author": "NASA, Apollo 17 crew", "licence": "Public domain", "url": "https://commons.wikimedia.org/wiki/File:The_Earth_seen_from_Apollo_17.jpg"},
    "sunflowers": {"author": "Vincent van Gogh", "licence": "Public domain", "url": "https://commons.wikimedia.org/wiki/File:Vincent_van_Gogh_-_Sunflowers_(1888,_National_Gallery_London).jpg"},
    "the-snail": {"author": "Tate, London", "licence": "Public domain in the EU", "note": "Public domain in the EU; in copyright in some other countries.", "source": "Tate", "url": "https://www.tate.org.uk/art/artworks/matisse-the-snail-t00540"},
    "mondrian-1930": {"author": "Piet Mondrian", "licence": "Public domain", "url": "https://commons.wikimedia.org/wiki/File:Piet_Mondriaan,_1930_-_Mondrian_Composition_II_in_Red,_Blue,_and_Yellow.jpg"},
}
CAR_IDS = {"countach"}
PHOTO_IDS = {"countach", "breakfast-at-tiffanys", "marilyn-1953", "blue-marble"}
ICON_IDS = ["countach", "breakfast-at-tiffanys", "marilyn-1953", "the-scream", "blue-marble"]
FLAT_IDS = {"mondrian-1930", "the-snail"}
STAGE_INFO = [
    ("blocking", "Blocking in"),
    ("form", "Form and color"),
    ("refinement", "Refinement"),
    ("detail", "Fine details"),
]


def smooth(image, sigma):
    if sigma <= 0:
        return image.copy()
    return gaussian_filter(image, sigma=(sigma, sigma, 0))


def bilinear(image, x, y):
    coords = np.array([[y], [x]])
    if image.ndim == 2:
        return float(map_coordinates(image, coords, order=1, mode="nearest")[0])
    return np.array([map_coordinates(image[..., c], coords, order=1, mode="nearest")[0] for c in range(image.shape[2])])


def flow_vector(pid, x, y, w, h):
    """Weak-structure flow, in image coordinates; strong contours override it."""
    nx, ny = x / w, y / h
    if pid == "starry-night":
        if ny < 0.62:
            vx, vy = 1.0, 0.10 * math.sin(nx * math.tau * 2.2)
            # Broad wind eddies plus tighter stellar halos.
            for cx, cy, radius, strength, spin in [
                (0.46, 0.30, 0.24, 2.6, 1),
                (0.68, 0.47, 0.19, 2.2, 1),
                (0.88, 0.17, 0.16, 1.4, -1),
                (0.35, 0.55, 0.14, 1.3, 1),
            ]:
                dx, dy = nx - cx, (ny - cy) * h / w
                r2 = dx * dx + dy * dy + 0.0007
                weight = strength * math.exp(-r2 / (radius * radius))
                vx += spin * -dy / math.sqrt(r2) * weight
                vy += spin * dx / math.sqrt(r2) * weight * w / h
            return np.array([vx, vy])
        if nx < 0.43 and ny < 0.99:
            return np.array([0.18 * math.sin(ny * 16), -1.0])
        return np.array([1.0, 0.12 * math.sin(nx * 15 + ny * 6)])
    if pid == "great-wave":
        if 0.06 < nx < 0.57 and 0.08 < ny < 0.67:
            dx, dy = nx - 0.32, (ny - 0.34) * h / w
            r = math.sqrt(dx * dx + dy * dy + 0.002)
            return np.array([-dy / r + 0.35, dx / r * w / h + 0.12])
        return np.array([1.0, 0.16 * math.sin(nx * 12 - ny * 5)])
    if pid == "the-scream":
        if ny < 0.36:
            # Long sky bands, disturbed into two broad structure-guided eddies.
            vx, vy = 1.0, 0.16 * math.sin(nx * math.tau * 2.0 + ny * 8.0)
            for cx, cy, radius, strength in [(0.28, 0.18, 0.18, 0.75), (0.72, 0.20, 0.22, 0.65)]:
                dx, dy = nx - cx, (ny - cy) * h / w
                r2 = dx * dx + dy * dy + 0.001
                weight = strength * math.exp(-r2 / (radius * radius))
                vx += -dy / math.sqrt(r2) * weight
                vy += dx / math.sqrt(r2) * weight * w / h
            return np.array([vx, vy])
        if ny > 0.50 + 0.48 * nx or ny > 0.90:
            return np.array([1.0, -0.62])
        return np.array([0.72, 0.18 * math.sin(nx * 9 - ny * 7)])
    if pid == "blue-marble":
        # Cloud currents curl around the major white systems; tensor tangents
        # remain dominant wherever the photograph supplies stable cloud edges.
        vx, vy = 0.55, 0.10
        for cx, cy, radius, strength, spin in [(0.31, 0.60, 0.24, 1.1, 1), (0.64, 0.72, 0.27, 1.0, -1), (0.55, 0.30, 0.18, 0.55, 1)]:
            dx, dy = nx - cx, ny - cy
            r2 = dx * dx + dy * dy + 0.001
            weight = strength * math.exp(-r2 / (radius * radius))
            vx += spin * -dy / math.sqrt(r2) * weight
            vy += spin * dx / math.sqrt(r2) * weight
        return np.array([vx, vy])
    if pid == "sunflowers":
        # Petal marks radiate from the nearest flower centre. Elsewhere the
        # painterly tangent field remains dominant, leaving vase and signature
        # transitions comparatively soft.
        if ny < 0.57 and 0.12 < nx < 0.90:
            centres = [(0.29, 0.18), (0.54, 0.15), (0.72, 0.27), (0.37, 0.36), (0.64, 0.43), (0.32, 0.50)]
            cx, cy = min(centres, key=lambda centre: (nx - centre[0]) ** 2 + ((ny - centre[1]) * REF_H / REF_W) ** 2)
            dx, dy = nx - cx, (ny - cy) * REF_H / REF_W
            length = math.hypot(dx, dy)
            if length > 0.006:
                return np.array([dx / length + 0.12, dy / length])
            return np.array([1.0, 0.2])
        return np.array([1.0, 0.06 * math.sin(ny * 12)])
    if pid == "van-gogh-self-portrait":
        if ny < 0.18 or nx < 0.24 or (nx > 0.82 and ny < 0.62):
            angle = 0.9 + 0.5 * math.sin(nx * 17 + ny * 11)
            return np.array([math.cos(angle), math.sin(angle)])
        return np.array([0.9, 0.25 + 0.14 * math.sin(ny * 20)])
    if pid == "mona-lisa":
        if 0.25 < nx < 0.75 and ny > 0.48:
            return np.array([0.65, 0.32])
        return np.array([0.85, 0.18 * math.sin(ny * 9 + nx * 4)])
    # Vermeer: folds descend, while the jacket has a broader diagonal grain.
    if ny < 0.55:
        return np.array([0.35 + 0.25 * math.sin(ny * 8), 1.0])
    return np.array([0.75, 0.45])


def tensor_tangents(field, sigma):
    gray = np.dot(field[..., :3], [0.2126, 0.7152, 0.0722])
    gy, gx = np.gradient(gray)
    smooth_sigma = max(0.7, sigma * 0.55)
    jxx = gaussian_filter(gx * gx, smooth_sigma)
    jyy = gaussian_filter(gy * gy, smooth_sigma)
    jxy = gaussian_filter(gx * gy, smooth_sigma)
    angle = 0.5 * np.arctan2(2 * jxy, jxx - jyy) + math.pi / 2
    coherence = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / (jxx + jyy + 1e-8)
    # Suppress JPEG grain: only stable geometry should steer a long mark.
    coherence = np.clip((coherence - 0.10) / 0.65, 0, 1)
    return np.stack([np.cos(angle), np.sin(angle)], axis=-1), coherence


def curved_path(pid, x, y, size, length, tangent, coherence, rng, curved=True):
    if not curved:
        tx, ty = tangent
        norm = math.hypot(tx, ty) or 1
        tx, ty = tx / norm, ty / norm
        return [x - tx * length / 2, y - ty * length / 2, x, y, x + tx * length / 2, y + ty * length / 2]
    vx, vy = flow_vector(pid, x, y, REF_W, REF_H)
    fallback = np.array([vx, vy], dtype=float)
    tangent = coherence * tangent + (1 - coherence) * fallback
    tangent /= max(1e-6, np.linalg.norm(tangent))
    # Follow the local field from the centre in both directions. Four segments
    # are enough to make a visible curve without bloating recipe files.
    forward = [(x, y)]
    backward = [(x, y)]
    step = length / 6.0
    for sign, points, direction in [(1, forward, 1), (-1, backward, -1)]:
        px, py = x, y
        tx, ty = tangent * direction
        for _ in range(3):
            px, py = px + tx * step, py + ty * step
            if not (0 <= px < REF_W and 0 <= py < REF_H):
                break
            points.append((px, py))
            local_t, local_c = bilinear(TANGENTS, px, py), float(bilinear(COHERENCE, px, py))
            local = flow_vector(pid, px, py, REF_W, REF_H)
            vec = local_c * local_t + (1 - local_c) * local
            vec /= max(1e-6, np.linalg.norm(vec))
            tx, ty = vec * direction
    ordered = list(reversed(backward[1:])) + forward
    return [round(float(v), 1) for point in ordered for v in point]


def choose_position(weight, rng, margin=0):
    flat = np.maximum(weight, 0).ravel().astype(np.float64)
    # Preserve exact zeros: subject masks use them as hard exclusions (notably
    # the black space around Blue Marble). Positive regions retain a tiny floor.
    flat = np.where(flat > 0, flat + max(float(flat.max()) * 0.00001, 1e-8), 0)
    flat /= flat.sum()
    index = int(rng.choice(flat.size, p=flat))
    y, x = divmod(index, REF_W)
    return float(x), float(y)


def path_colour(field, path):
    points = np.asarray(path).reshape(-1, 2)
    colours = []
    for x, y in points[::max(1, len(points) // 3)]:
        colours.append(bilinear(field, np.clip(x, 0, REF_W - 1), np.clip(y, 0, REF_H - 1)))
    colour = np.mean(colours, axis=0)
    return "#" + "".join(f"{int(np.clip(round(c * 255), 0, 255)):02x}" for c in colour)


def make_stroke(pid, field, weight, size_range, length_range, opacity_range, rng, curved, detail=False, disc=None):
    x, y = choose_position(weight, rng)
    size = float(rng.uniform(*size_range))
    local_gradient = float(np.hypot(bilinear(GX, x, y), bilinear(GY, x, y)))
    if detail and local_gradient < 0.18:
        size = max(1.5, size * 0.65)
    tangent = bilinear(TANGENTS, x, y)
    coherence = float(bilinear(COHERENCE, x, y))
    length = size * float(rng.uniform(*length_range))
    if pid == "the-scream":
        nx, ny = x / REF_W, y / REF_H
        if (ny > 0.50 + 0.48 * nx and nx < 0.72) or ny > 0.90:
            curved = False
            tangent = np.array([1.0, -0.62])
    path = curved_path(pid, x, y, size, length, tangent, coherence, rng, curved)
    if disc is not None:
        cx, cy, radius = disc
        safe_radius = max(2.0, radius - size * 0.58)
        points = np.asarray(path, dtype=float).reshape(-1, 2)
        delta = points - np.array([cx, cy])
        distance = np.linalg.norm(delta, axis=1)
        scale = np.minimum(1.0, safe_radius / np.maximum(distance, 1e-6))
        points = np.array([cx, cy]) + delta * scale[:, None]
        path = [round(float(v), 1) for point in points for v in point]
    return {
        "p": path,
        "c": path_colour(field, path),
        "s": round(size, 1),
        "o": round(float(rng.uniform(*opacity_range)), 2),
    }


def base_weight(field, stage_index, previous=None):
    gray = np.dot(field[..., :3], [0.2126, 0.7152, 0.0722])
    gy, gx = np.gradient(gray)
    edge = np.hypot(gx, gy)
    colour_change = np.zeros_like(gray) if previous is None else np.mean(np.abs(field - previous), axis=-1)
    if stage_index == 0:
        weight = 0.3 + colour_change * 1.5 + edge * 0.4
    elif stage_index == 1:
        weight = 0.10 + colour_change * 5.0 + edge * 0.8
    elif stage_index == 2:
        weight = 0.025 + colour_change * 5.5 + edge * 1.5
    else:
        weight = 0.005 + colour_change * 4.0 + edge * 2.4
    # Keep coordinates random but ensure all large colour regions participate.
    return gaussian_filter(weight, max(0.4, [14, 5, 1.5, 0.5][stage_index]))


def scaled_counts(base, total):
    counts = [round(count * total / 5000) for count in base]
    counts[2] += total - sum(counts)
    return counts


def _weighted_bounds(axis, weights, low=0.02, high=0.98):
    cumulative = np.cumsum(weights)
    total = cumulative[-1]
    if total <= 0:
        return 0.0, 1.0
    return tuple(float(np.interp(fraction * total, cumulative, np.arange(len(axis)))) / max(1, len(axis) - 1) for fraction in (low, high))


def car_subject_mask(reference):
    """Infer the central vehicle's box from colour contrast and edge energy."""
    height, width = reference.shape[:2]
    structural = smooth(reference, 4.0)
    gray = np.dot(structural, [0.2126, 0.7152, 0.0722])
    gy, gx = np.gradient(gray)
    edge = gaussian_filter(np.hypot(gx, gy), 3.0)
    border_width = max(2, round(min(height, width) * 0.04))
    border = np.concatenate([reference[:border_width].reshape(-1, 3), reference[-border_width:].reshape(-1, 3), reference[:, :border_width].reshape(-1, 3), reference[:, -border_width:].reshape(-1, 3)])
    border_colour = np.median(border, axis=0)
    contrast = gaussian_filter(np.linalg.norm(reference - border_colour, axis=-1), 5.0)
    yy, xx = np.mgrid[0:height, 0:width]
    nx, ny = xx / max(1, width - 1), yy / max(1, height - 1)
    centre_prior = np.exp(-((nx - 0.5) / 0.54) ** 4 - ((ny - 0.55) / 0.62) ** 4)
    energy = gaussian_filter((edge * 4.0 + contrast * 0.42) * centre_prior, 5.0) + 1e-8
    x0, x1 = _weighted_bounds(nx[0], energy.sum(axis=0))
    y0, y1 = _weighted_bounds(ny[:, 0], energy.sum(axis=1))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rx, ry = max(0.18, (x1 - x0) / 2), max(0.16, (y1 - y0) / 2)
    radius2 = ((nx - cx) / rx) ** 2 + ((ny - cy) / ry) ** 2
    return (1.0 / (1.0 + np.exp(np.clip((radius2 - 0.9) * 7.0, -40, 40)))).astype(np.float32)


def car_weight(weight, field, mask, stage_index):
    gray = np.dot(field[..., :3], [0.2126, 0.7152, 0.0722])
    gy, gx = np.gradient(gray)
    edge = np.hypot(gx, gy)
    focus = [0.55, 0.08, 0.025][stage_index - 1] + [1.8, 3.8, 6.0][stage_index - 1] * mask
    return weight * focus + edge * (0.12 + [1.2, 2.5, 4.0][stage_index - 1] * mask)


def audrey_subject_mask(reference):
    """Find Hepburn's dark figure in the central column, including head/hands."""
    height, width = reference.shape[:2]
    structural = smooth(reference, 0.8)
    gray = np.dot(structural, [0.2126, 0.7152, 0.0722])
    yy, xx = np.mgrid[0:height, 0:width]
    nx, ny = xx / width, yy / height
    # The patterned folding screen occupies the sides. Restrict darkness to the
    # narrow figure column, then add the brighter face/hair and thin holder.
    column = np.exp(-((nx - 0.445) / 0.150) ** 6)
    vertical = np.clip((ny - 0.10) / 0.05, 0, 1) * np.clip((0.97 - ny) / 0.05, 0, 1)
    darkness = np.clip((0.53 - gray) / 0.30, 0, 1)
    figure = darkness * column * vertical
    head = np.exp(-(((nx - 0.480) / 0.064) ** 2 + ((ny - 0.208) / 0.064) ** 2) * 1.4)
    # The holder runs left from the gloved hand. A soft capsule keeps its sparse
    # bright/dark contour eligible for fine detail without admitting the screen.
    ax, ay, bx, by = 0.155, 0.267, 0.370, 0.269
    dx, dy = bx - ax, by - ay
    t = np.clip(((nx - ax) * dx + (ny - ay) * dy) / (dx * dx + dy * dy), 0, 1)
    holder_distance = np.hypot(nx - (ax + t * dx), ny - (ay + t * dy))
    holder = np.exp(-(holder_distance / 0.014) ** 2) * 0.85
    mask = np.maximum.reduce([figure, head, holder])
    return np.clip(gaussian_filter(mask, 1.3) * 1.5, 0, 1).astype(np.float32)


def audrey_feature_mask(reference):
    """Small identity features that must survive thumbnail-scale rendering."""
    height, width = reference.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width]
    nx, ny = xx / width, yy / height
    face_bun = np.exp(-(((nx - 0.480) / 0.067) ** 2 + ((ny - 0.208) / 0.070) ** 2) * 1.2)
    gloves = np.exp(-(((nx - 0.350) / 0.066) ** 2 + ((ny - 0.310) / 0.115) ** 2) * 1.4)
    ax, ay, bx, by = 0.155, 0.267, 0.370, 0.269
    dx, dy = bx - ax, by - ay
    t = np.clip(((nx - ax) * dx + (ny - ay) * dy) / (dx * dx + dy * dy), 0, 1)
    holder_distance = np.hypot(nx - (ax + t * dx), ny - (ay + t * dy))
    holder = np.exp(-(holder_distance / 0.012) ** 2)
    return np.maximum.reduce([face_bun, gloves, holder]).astype(np.float32)


def blue_marble_disc(reference):
    """Measure the bright terrestrial disc against black space."""
    gray = np.dot(smooth(reference, 2.0), [0.2126, 0.7152, 0.0722])
    bright = gray > 0.12
    yy, xx = np.nonzero(bright)
    cx, cy = float(xx.mean()), float(yy.mean())
    radius = math.sqrt(float(bright.sum()) / math.pi)
    h, w = gray.shape
    y, x = np.mgrid[0:h, 0:w]
    distance = radius - np.hypot(x - cx, y - cy)
    # A six-pixel soft membership band excludes all black background samples.
    mask = np.clip(distance / 6.0, 0, 1).astype(np.float32)
    return mask, (cx, cy, radius)


def blue_marble_weight(reference, field, weight, mask, stage_index):
    """Concentrate cloud whites and the Africa/Arabia ochres inside the disc."""
    gray = np.dot(field[..., :3], [0.2126, 0.7152, 0.0722])
    red, green, blue = field[..., 0], field[..., 1], field[..., 2]
    saturation = np.max(field, axis=-1) - np.min(field, axis=-1)
    cloud = np.clip((gray - 0.48) / 0.34, 0, 1) * np.clip((0.42 - saturation) / 0.28, 0.2, 1)
    h, w = gray.shape
    yy, xx = np.mgrid[0:h, 0:w]
    nx, ny = xx / w, yy / h
    africa_arabia = np.exp(-(((nx - 0.565) / 0.19) ** 2 + ((ny - 0.315) / 0.22) ** 2) * 1.3)
    ochre = np.clip((red - blue - 0.015) * 4.5, 0, 1) * africa_arabia
    cloud_gain = [0.45, 1.8, 3.2, 4.5][stage_index]
    land_gain = [0.35, 1.2, 2.2, 3.0][stage_index]
    focused = weight * (0.45 + cloud_gain * cloud + land_gain * ochre) + 0.08 * cloud + 0.07 * ochre
    return focused * mask


def portrait_weight(reference, field, weight, stage_index, pid):
    """Prioritise fine clustered contours: eyes, lips, hair and dark silhouettes."""
    fine = smooth(reference, 0.45)
    gray = np.dot(fine, [0.2126, 0.7152, 0.0722])
    gy, gx = np.gradient(gray)
    fine_edge = np.hypot(gx, gy)
    feature_density = gaussian_filter(fine_edge, 1.2)
    height, width = gray.shape
    yy, xx = np.mgrid[0:height, 0:width]
    centre = np.exp(-((xx / width - 0.5) / 0.34) ** 2 - ((yy / height - 0.48) / 0.52) ** 2)
    weight = weight * (0.45 + 1.4 * centre) + fine_edge * 1.1 + feature_density * (1.4 if stage_index == 2 else 2.8)
    if pid == "breakfast-at-tiffanys":
        # The black dress and its bright, thin neighbouring contours (including
        # the holder) are the identifying full-length features in this still.
        darkness = np.clip((0.34 - gray) / 0.34, 0, 1) * centre
        weight += darkness * (0.45 if stage_index == 2 else 1.1)
    return weight


def residual_weight(reference, render):
    residual = np.mean(np.abs(reference - render), axis=-1)
    edge = np.hypot(sobel(np.dot(reference, [0.2126, 0.7152, 0.0722])), sobel(np.dot(render, [0.2126, 0.7152, 0.0722])))
    return gaussian_filter(0.002 + residual * 4.5 + edge * 0.22, 1.0)


def plan(pid, residual_render=None, seed=1729, strokes=5000):
    global REF_W, REF_H, TANGENTS, COHERENCE, GX, GY
    if pid in FLAT_IDS:
        from plan_flat import flat_plan
        return flat_plan(pid, *META[pid], CREDITS[pid], strokes)
    rng = np.random.default_rng(seed + sum(ord(c) for c in pid))
    reference_path = ROOT / "references" / f"{pid}.jpg"
    reference = np.asarray(Image.open(reference_path).convert("RGB"), dtype=np.float32) / 255.0
    REF_H, REF_W = reference.shape[:2]
    title, artist, year = META[pid]
    portrait = pid in ("mona-lisa", "girl-with-a-pearl-earring", "breakfast-at-tiffanys", "marilyn-1953")
    car = pid in CAR_IDS
    photo = pid in PHOTO_IDS
    woodcut = pid == "great-wave"

    if portrait:
        counts = [420, 1500, 2300, 780]
        sigmas = [14, 5.0, 1.55, 0.55]
        sizes = [(64, 150), (19, 43), (5.5, 14), (2.2, 5.4)]
        lengths = [(1.2, 2.4), (0.8, 1.8), (0.75, 1.55), (0.65, 1.5)]
        opacity = [(0.84, 1.0), (0.80, 0.99), (0.78, 0.98), (0.78, 0.98)]
    elif pid == "blue-marble":
        counts = [280, 1120, 2200, 1400]
        sigmas = [12, 3.8, 1.0, 0.32]
        sizes = [(50, 110), (14, 32), (3.5, 10.0), (1.4, 4.2)]
        lengths = [(0.8, 1.5), (0.7, 1.4), (0.8, 1.6), (0.7, 1.5)]
        opacity = [(0.90, 1.0), (0.84, 0.99), (0.82, 0.99), (0.84, 1.0)]
    elif car:
        counts = [350, 1250, 2000, 1400]
        sigmas = [11, 3.6, 0.95, 0.32]
        sizes = [(58, 132), (16, 38), (4.0, 11.5), (1.6, 5.2)]
        lengths = [(1.4, 2.7), (1.0, 2.1), (0.9, 1.8), (0.8, 1.8)]
        opacity = [(0.88, 1.0), (0.83, 0.99), (0.82, 0.99), (0.84, 1.0)]
    elif woodcut:
        counts = [350, 1200, 1850, 1600]
        sigmas = [13, 4.0, 1.0, 0.30]
        sizes = [(60, 130), (17, 39), (4.5, 12), (1.8, 5.2)]
        lengths = [(1.4, 2.6), (0.85, 1.8), (0.85, 1.65), (0.85, 1.75)]
        opacity = [(0.88, 1.0), (0.83, 0.99), (0.82, 0.99), (0.86, 1.0)]
    else:
        counts = [350, 1250, 2000, 1400]
        sigmas = [13, 4.2, 1.15, 0.45]
        sizes = [(58, 132), (16, 38), (4.2, 12.5), (1.8, 6.0)]
        lengths = [(1.4, 2.7), (1.0, 2.1), (0.9, 1.8), (0.8, 1.8)]
        opacity = [(0.85, 1.0), (0.80, 0.99), (0.78, 0.98), (0.80, 0.99)]

    counts = scaled_counts(counts, strokes)
    if (photo or pid == "sunflowers") and strokes != 5000:
        # Reduced recipes need enough paint area to cover the large flat regions.
        # Fine marks keep their original sizes so wheels and facial features stay crisp.
        budget_scale = min(1.35, (5000 / strokes) ** 0.22)
        sizes = [tuple(value * budget_scale for value in size_range) if index < 3 else size_range for index, size_range in enumerate(sizes)]
        if car:
            contour_scale = min(1.65, (5000 / strokes) ** 0.35)
            lengths = [tuple(value * contour_scale for value in length_range) if index >= 2 else length_range for index, length_range in enumerate(lengths)]
        opacity_boost = 0.70 * (1 - strokes / 5000)
        opacity = [tuple(min(1.0, value + (1 - value) * opacity_boost) for value in opacity_range) for opacity_range in opacity]

    fields = [smooth(reference, sigma) for sigma in sigmas]
    GX, GY = np.gradient(np.dot(reference, [0.2126, 0.7152, 0.0722]))
    residual = None
    if residual_render:
        rendered = np.asarray(Image.open(residual_render).convert("RGB"), dtype=np.float32) / 255.0
        residual = residual_weight(reference, rendered)
        # Residual repair is a distinct stage; earlier broad stages stay stable
        # so variants are comparable and the best recipe can be retained.
        counts = [0, 0, 0, strokes]

    recipe = {
        "id": pid,
        "title": title,
        "artist": artist,
        "year": year,
        "width": REF_W,
        "height": REF_H,
        "ground": "#000000" if pid == "blue-marble" else "#d8d7d3" if pid == "breakfast-at-tiffanys" else "#ffffff" if not photo else "#" + "".join(f"{round(channel * 255):02x}" for channel in np.median(reference.reshape(-1, 3), axis=0)),
        "reference": f"../references/{pid}.jpg",
        "seed": seed,
        "planner": "multiscale structure-tensor flow, stochastic grid-free sampling, opacity-softened round strokes",
        "stages": [],
    }
    if photo:
        recipe["profile"] = "photo"
        recipe["planner"] += "; centred photographic subject/detail weighting"
    if pid == "sunflowers":
        recipe["profile"] = "painterly"
        recipe["planner"] += "; radial petal impasto and soft vase/signature transitions"
    if pid in CREDITS:
        recipe["credit"] = CREDITS[pid]
    if pid == "blue-marble":
        recipe["planner"] += "; brightness-derived disc mask, tangent-following cloud swirls and Africa/Arabia weighting"
    if pid == "the-scream":
        recipe["planner"] += "; structure-tensor sky bands and straight diagonal bridge marks"
    previous = None
    subject_mask = car_subject_mask(reference) if car else None
    audrey_mask = audrey_subject_mask(reference) if pid == "breakfast-at-tiffanys" else None
    audrey_features = audrey_feature_mask(reference) if pid == "breakfast-at-tiffanys" else None
    disc_mask, disc = blue_marble_disc(reference) if pid == "blue-marble" else (None, None)
    for index, ((stage_id, label), count) in enumerate(zip(STAGE_INFO, counts)):
        field = fields[index]
        if pid == "breakfast-at-tiffanys":
            # Screen colour comes only from a heavily blurred field: no lattice
            # survives into its sparse, soft pale blocks. Figure marks stay sharp.
            screen_field = smooth(reference, 13.0 if index < 2 else 16.0)
            field = field * audrey_mask[..., None] + screen_field * (1 - audrey_mask[..., None])
        TANGENTS, COHERENCE = tensor_tangents(field, sigmas[index] if not residual else 1.0)
        weight = residual if residual is not None else base_weight(field, index, previous)
        if residual is None and photo:
            if car and index >= 1:
                weight = car_weight(weight, field, subject_mask, index)
            elif portrait and index >= 2:
                weight = portrait_weight(reference, field, weight, index, pid)
        if pid == "blue-marble":
            weight = blue_marble_weight(reference, fields[index], weight, disc_mask, index)
        if pid == "sunflowers" and index >= 1:
            yy, xx = np.mgrid[0:REF_H, 0:REF_W]
            petal_zone = np.clip((0.59 - yy / REF_H) / 0.10, 0, 1)
            red, green, blue = fields[index][..., 0], fields[index][..., 1], fields[index][..., 2]
            yellow = np.clip((red + green) * 0.5 - blue, 0, 0.65) * petal_zone
            weight *= 1.0 + yellow * (1.0 if index == 1 else 2.0)
        strokes = []
        if pid == "breakfast-at-tiffanys" and index >= 1 and residual is None:
            figure_count = round(count * (0.55 if index == 1 else 0.70))
            darkness = np.clip((0.42 - np.dot(fields[index], [0.2126, 0.7152, 0.0722])) / 0.32, 0, 1)
            figure_weight = (weight + darkness * (1.6 if index == 2 else 2.6)) * audrey_mask
            figure_weight += audrey_features * (1.2 if index == 1 else 3.0 if index == 2 else 6.0)
            figure_weight *= audrey_mask
            screen_weight = gaussian_filter(weight + 0.10, 5.0) * (1 - audrey_mask)
            assignments = [(figure_count, figure_weight, True), (count - figure_count, screen_weight, False)]
            for part_count, part_weight, is_figure in assignments:
                for _ in range(part_count):
                    if is_figure:
                        figure_sizes = (10.0, 26.0) if index == 1 else sizes[index]
                        figure_lengths = (0.70, 1.40) if index == 1 else lengths[index]
                        stroke = make_stroke(pid, fields[index], part_weight, figure_sizes, figure_lengths, (0.91, 1.0), rng, True, index == 3)
                        # Sampling the figure centre avoids averaging a dark dress
                        # or glove with the pale screen across a silhouette edge.
                        points = stroke["p"]
                        middle = len(points) // 2
                        centre_x, centre_y = points[middle - middle % 2], points[middle - middle % 2 + 1]
                        centre_colour = bilinear(fields[index], np.clip(centre_x, 0, REF_W - 1), np.clip(centre_y, 0, REF_H - 1))
                        stroke["c"] = "#" + "".join(f"{int(np.clip(round(c * 255), 0, 255)):02x}" for c in centre_colour)
                    else:
                        soft_sizes = (18.0, 42.0) if index == 1 else (12.0, 30.0) if index == 2 else (7.0, 18.0)
                        stroke = make_stroke(pid, screen_field, part_weight, soft_sizes, (0.65, 1.25), (0.48, 0.76), rng, False)
                    stroke["stage"] = stage_id
                    strokes.append(stroke)
        else:
            for _ in range(count):
                if residual is not None:
                    stroke = make_stroke(pid, field, weight, (1.4, 5.4), (0.7, 1.6), (0.67, 0.90), rng, True, True, disc=disc)
                else:
                    stroke = make_stroke(pid, field, weight, sizes[index], lengths[index], opacity[index], rng, index != 0 and not (car and index == 3), index == 3, disc=disc)
                stroke["stage"] = stage_id
                strokes.append(stroke)
        recipe["stages"].append({"id": stage_id, "label": label, "strokes": strokes})
        previous = field
    # Keep all four semantic stages, including empty ones in repair variants.
    recipe["strokeCount"] = sum(len(stage["strokes"]) for stage in recipe["stages"])
    return recipe


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("painting", choices=list(META) + ["all"])
    parser.add_argument("--residual", type=Path, help="Existing render; distribute a 5000-stroke fine repair variant by image error")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", type=int, default=1729)
    parser.add_argument("--strokes", type=int, default=5000, help="Total stroke budget scaled across four stages (flat: 500–5,000; Sunflowers: 2,500–5,000; others: 1,500–5,000)")
    args = parser.parse_args()
    ids = list(META) if args.painting == "all" else [args.painting]
    for pid in ids:
        minimum = 500 if pid in FLAT_IDS else 2500 if pid == "sunflowers" else 1500
        if not minimum <= args.strokes <= 5000:
            parser.error(f"--strokes must be between {minimum:,} and 5,000 for {pid}")
    for pid in ids:
        recipe = plan(pid, args.residual, args.seed, args.strokes)
        output = args.output or ROOT / "recipes" / f"{pid}.json"
        output.write_text(json.dumps(recipe, separators=(",", ":")) + "\n")
        print(json.dumps({"recipe": str(output), "strokes": recipe["strokeCount"], "stages": [len(s["strokes"]) for s in recipe["stages"]]}))


if __name__ == "__main__":
    main()
