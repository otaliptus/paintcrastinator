#!/usr/bin/env python3
"""Claude's refinement pass for the 5,000-stroke recipes (not one of Kimi's tools).

Keeps the recipe's first two stages (blocking in, form) exactly, then re-plans the
refinement and detail stages greedily: each new stroke goes where the painting is
furthest from the reference, follows the local structure direction, takes the
reference colour, and is kept only if it lowers the error. Same stage sizes, so the
recipe keeps its 5,000 strokes and four stages.

The search uses a NumPy model of app/brush.js (a soft round stamp repeated along the
path; for one colour, repeated source-over equals c + (C - c) * prod(1 - a_i)).
The final render and score always come from the real Chromium renderer and score.py.

Usage: refine5k.py <id> <base.png> <out.json> [seed]
  base.png = Chromium render of the recipe's first two stages.
"""
import json, sys, os
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, sobel, zoom

pid, base_png, out_json = sys.argv[1:4]
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 7
ROOT = "/home/node/.openclaw/workspace/painting-cookbook/"
rng = np.random.default_rng(seed)
import os as _os
recipe = json.load(open(_os.environ.get("RECIPE") or f"{ROOT}recipes/{pid}.json"))
W, H = recipe["width"], recipe["height"]
ref = np.asarray(Image.open(f"{ROOT}references/{pid}.jpg").convert("RGB").resize((W, H), Image.LANCZOS), dtype=np.float32)
canvas = np.asarray(Image.open(base_png).convert("RGB"), dtype=np.float32).copy()
assert canvas.shape == ref.shape, (canvas.shape, ref.shape)

# Structure direction (tangent = perpendicular to the smoothed gradient) and coherence.
gray = ref @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
gx, gy = sobel(gray, 1), sobel(gray, 0)
jxx, jyy, jxy = (gaussian_filter(v, 3) for v in (gx * gx, gy * gy, gx * gy))
theta = 0.5 * np.arctan2(2 * jxy, jxx - jyy) + np.pi / 2
coherence = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / (jxx + jyy + 1e-6)
edges = np.hypot(gx, gy)
edges = edges / (np.percentile(edges, 99) + 1e-6)

PROFILE_T = np.array([0, .28, .62, .84, 1.0])
PROFILE_A = np.array([1, .98, .82, .43, 0.0])
blurred_refs = {}

def ref_blur(sigma):
    key = round(sigma * 2) / 2
    if key not in blurred_refs:
        blurred_refs[key] = np.stack([gaussian_filter(ref[..., c], key) for c in range(3)], -1) if key > 0 else ref
    return blurred_refs[key]

def stamps_along(points, size):
    spacing = max(0.25, size * 0.25)
    out = [points[0]]
    carry = 0.0
    for (ax, ay), (bx, by) in zip(points[:-1], points[1:]):
        length = np.hypot(bx - ax, by - ay)
        if not length:
            continue
        d = spacing if carry == 0 else spacing - carry
        while d <= length:
            t = d / length
            out.append((ax + (bx - ax) * t, ay + (by - ay) * t))
            d += spacing
        carry = (carry + length) % spacing
    out.append(points[-1])
    return out

def transmittance(points, size, opacity):
    """Per-pixel product of (1 - stamp alpha) over the stroke's bounding box."""
    radius = max(1, round(size * 4) / 4) / 2
    xs = [p[0] for p in points]; ys = [p[1] for p in points]
    x0 = max(0, int(np.floor(min(xs) - radius - 1))); x1 = min(W, int(np.ceil(max(xs) + radius + 2)))
    y0 = max(0, int(np.floor(min(ys) - radius - 1))); y1 = min(H, int(np.ceil(max(ys) + radius + 2)))
    if x1 <= x0 or y1 <= y0:
        return None
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32) + 0.5
    T = np.ones_like(xx)
    for cx, cy in stamps_along(points, size):
        r = np.hypot(xx - cx, yy - cy) / radius
        a = np.interp(r, PROFILE_T, PROFILE_A).astype(np.float32) * opacity
        T *= 1 - a
    return (y0, y1, x0, x1), T

def trace(cx, cy, length, steps=3):
    """A short streamline through (cx, cy) along the tangent field, centred on the point."""
    def walk(sign):
        pts, x, y = [], cx, cy
        prev = None
        for _ in range(steps):
            t = theta[int(min(H - 1, max(0, y))), int(min(W - 1, max(0, x)))]
            d = np.array([np.cos(t), np.sin(t)]) * sign
            if prev is not None and d @ prev < 0:
                d = -d
            prev = d
            x, y = x + d[0] * length / (2 * steps), y + d[1] * length / (2 * steps)
            pts.append((float(np.clip(x, 0, W - 1)), float(np.clip(y, 0, H - 1))))
        return pts
    back = walk(-1)[::-1]
    return back + [(float(cx), float(cy))] + walk(1)

def error_map():
    e = ((canvas - ref) ** 2).sum(-1)
    return gaussian_filter(e * (1 + 1.5 * edges), 2)

CANDIDATES = int(os.environ.get("CANDIDATES", "24"))
NUDGES = int(os.environ.get("NUDGES", "10"))

def evaluate(pts, s):
    """Best colour for this stroke (least squares) and the error it removes."""
    res = transmittance(pts, s, 1.0)
    if res is None:
        return None
    (y0, y1, x0, x1), T = res
    patch = canvas[y0:y1, x0:x1]
    target = ref[y0:y1, x0:x1]
    A = (1 - T)[..., None]
    denom = float((A * A).sum())
    if denom < 1e-3:
        return None
    colour = np.clip((A * (target - patch * T[..., None])).sum((0, 1)) / denom, 0, 255)
    new = colour + (patch - colour) * T[..., None]
    gain = float(((patch - target) ** 2).sum() - ((new - target) ** 2).sum())
    return gain, colour, (y0, y1, x0, x1), new

def make_path(cx, cy, s, length, mode, angle=None):
    if mode == "trace":
        return trace(cx, cy, length)
    a = theta[int(min(H - 1, max(0, cy))), int(min(W - 1, max(0, cx)))] if angle is None else angle
    dx, dy = np.cos(a) * length / 2, np.sin(a) * length / 2
    return [(float(np.clip(cx - dx, 0, W - 1)), float(np.clip(cy - dy, 0, H - 1))), (float(cx), float(cy)), (float(np.clip(cx + dx, 0, W - 1)), float(np.clip(cy + dy, 0, H - 1)))]

def plan_stage(count, size_from, size_to, label):
    global canvas
    strokes = []
    for i in range(count):
        if i % 50 == 0:
            emap = error_map()
            small = zoom(emap, 0.25, order=1)
            prob = small.ravel() ** 1.5
            prob /= prob.sum()
            ph, pw = small.shape
        frac = i / max(1, count - 1)
        size = size_from * (size_to / size_from) ** frac
        best = None
        for attempt in range(CANDIDATES):
            k = rng.choice(prob.size, p=prob)
            cy = (k // pw + rng.random()) * H / ph
            cx = (k % pw + rng.random()) * W / pw
            s = size * rng.uniform(0.7, 1.35)
            coh = coherence[int(min(H - 1, cy)), int(min(W - 1, cx))]
            length = s * (1.0 + 5.0 * min(1.0, coh) * rng.uniform(0.3, 1.0))
            mode = ("trace", "straight", "angle")[attempt % 3]
            angle = rng.uniform(0, np.pi) if mode == "angle" else None
            pts = make_path(cx, cy, s, length, mode, angle)
            r = evaluate(pts, s)
            if r and (best is None or r[0] > best[0]):
                best = (*r, pts, s, (cx, cy, length, mode, angle))
        # Nudge the best candidate: position, size, length, angle.
        for _ in range(NUDGES):
            cx, cy, length, mode, angle = best[6]
            s = best[5] * rng.uniform(0.85, 1.18)
            cx2 = float(np.clip(cx + rng.normal(0, s * 0.3), 0, W - 1)); cy2 = float(np.clip(cy + rng.normal(0, s * 0.3), 0, H - 1))
            length2 = max(s, length * rng.uniform(0.8, 1.25))
            mode2 = "angle" if mode != "trace" else mode
            ang = theta[int(cy), int(cx)] if angle is None else angle
            angle2 = ang + rng.normal(0, 0.2) if mode2 == "angle" else None
            pts = make_path(cx2, cy2, s, length2, mode2, angle2)
            r = evaluate(pts, s)
            if r and r[0] > best[0]:
                best = (*r, pts, s, (cx2, cy2, length2, mode2, angle2))
        gain, colour, (y0, y1, x0, x1), new, pts, s, _ = best
        canvas[y0:y1, x0:x1] = new
        hexc = "#%02x%02x%02x" % tuple(int(np.clip(round(v), 0, 255)) for v in colour)
        flat = [round(v, 1) for p in pts for v in p]
        strokes.append({"p": flat, "c": hexc, "s": round(float(s), 2), "o": 1})
    print(f"{label}: {count} strokes", flush=True)
    return strokes

import os
stages = recipe["stages"]
keep = int(os.environ.get("KEEP", "2"))
portrait = pid in ("mona-lisa", "girl-with-a-pearl-earring", "marilyn-1953", "van-gogh-self-portrait")
if keep == 0:
    # Plan every stage from the blank ground: four stages, big to small.
    total = int(os.environ.get("TOTAL") or sum(len(s["strokes"]) for s in stages))
    small = total < 1200
    n1 = total // (5 if small else 8); n2 = total * 3 // 10; n3 = total * 3 // 10; n4 = total - n1 - n2 - n3
    if os.environ.get("SPLIT"):
        # e.g. SPLIT=0.06,0.14,0.30 -> mostly fine work
        f1, f2, f3 = (float(v) for v in os.environ["SPLIT"].split(","))
        n1 = int(total * f1); n2 = int(total * f2); n3 = int(total * f3); n4 = total - n1 - n2 - n3
    # Stroke size scales with the budget: fewer strokes must be bigger to cover the canvas.
    base = (W * H / total) ** 0.5
    labels = [("blocking", "Blocking in"), ("form", "Form and color"), ("refinement", "Refinement"), ("detail", "Fine details")]
    tips = [s.get("tip", "") for s in stages[:4]] + [""] * 4
    mn = float(os.environ.get("MINSIZE", "2.0"))
    if small:
        plans = [(n1, 3.2 * base, 1.6 * base), (n2, 1.6 * base, 0.8 * base), (n3, 0.8 * base, 0.4 * base), (n4, 0.4 * base, max(mn, 0.18 * base))]
    else:
        plans = [(n1, 70, 26), (n2, 26, 10), (n3, 10, 4.5), (n4, 4.5, mn)]
    recipe["stages"] = stages = [{"id": labels[k][0], "label": labels[k][1], "tip": tips[k], "strokes": plan_stage(n, a, b, labels[k][0])} for k, (n, a, b) in enumerate(plans)]
elif keep == 1:
    # Re-plan stages 2-4 too: split the remaining budget evenly, big to small.
    rest = int(os.environ["TOTAL"]) - len(stages[0]["strokes"]) if os.environ.get("TOTAL") else sum(len(s["strokes"]) for s in stages[1:])
    n2 = rest // 3; n3 = rest // 3; n4 = rest - n2 - n3
    stages[1]["strokes"] = plan_stage(n2, 26, 10, "form")
    stages[2]["strokes"] = plan_stage(n3, 10, 4.5, "refinement")
    stages[3]["strokes"] = plan_stage(n4, 4.5, float(os.environ.get("MINSIZE", "2.0")), "detail")
else:
    n3, n4 = len(stages[2]["strokes"]), len(stages[3]["strokes"])
    stages[2]["strokes"] = plan_stage(n3, 18 if not portrait else 14, 6, "refinement")
    stages[3]["strokes"] = plan_stage(n4, 6, 2.4, "detail")
recipe["planner"] = (recipe.get("planner") or "") + " + Claude greedy error-driven refinement/detail"
recipe["strokeCount"] = sum(len(s["strokes"]) for s in stages)
json.dump(recipe, open(out_json, "w"), separators=(",", ":"))
Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8)).save(out_json.replace(".json", ".model.png"))
print("wrote", out_json, recipe["strokeCount"])
