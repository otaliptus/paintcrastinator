#!/usr/bin/env python3
"""One conservative residual-feedback colour planning pass.

Geometry stays untouched. Stroke colours are adjusted from the difference between
the actual shared-engine render and reference along each path, clamped to a
limited correction so the result remains a painterly recipe rather than pixels.
Only candidates with a higher composite score are promoted.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates

import plan
from score import score
from refine import render

ROOT = Path(__file__).resolve().parents[1]


def samples(image, stroke):
    points = np.asarray(stroke["p"], dtype=float).reshape(-1, 2)
    if len(points) > 3:
        points = points[[0, len(points) // 2, -1]]
    coords = np.array([points[:, 1], points[:, 0]])
    return np.stack([map_coordinates(image[..., channel], coords, order=1, mode="nearest") for channel in range(3)], axis=-1).mean(axis=0)


def recolour(pid, gain=0.38):
    base_path = ROOT / "recipes" / f"{pid}.json"
    recipe = json.loads(base_path.read_text())
    reference = np.asarray(Image.open(ROOT / "references" / f"{pid}.jpg").convert("RGB"), dtype=np.float32) / 255.0
    rendered = np.asarray(Image.open(ROOT / "recipes" / f"{pid}.png").convert("RGB"), dtype=np.float32) / 255.0
    # Broad underpainting remains stable; only the marks small enough to respond
    # to local residual are corrected.
    for stage in recipe["stages"][1:]:
        for stroke in stage["strokes"]:
            old = np.array([int(stroke["c"][i:i + 2], 16) for i in (1, 3, 5)], dtype=float) / 255.0
            target = samples(reference, stroke)
            actual = samples(rendered, stroke)
            opacity = max(0.55, stroke["o"])
            correction = np.clip((target - actual) / opacity, -0.16, 0.16)
            new = np.clip(old + gain * correction, 0, 1)
            stroke["c"] = "#" + "".join(f"{round(channel * 255):02x}" for channel in new)
    recipe["planner"] += f"; residual colour feedback gain {gain}"
    variant_dir = ROOT / "recipes" / "variants"
    variant_dir.mkdir(exist_ok=True)
    variant_path = variant_dir / f"{pid}-recolour.json"
    variant_png = variant_dir / f"{pid}-recolour.png"
    variant_score_path = variant_dir / f"{pid}-recolour.score.json"
    variant_path.write_text(json.dumps(recipe, separators=(",", ":")) + "\n")
    render(variant_path, variant_png)
    result = score(ROOT / "references" / f"{pid}.jpg", variant_png)
    variant_score_path.write_text(json.dumps(result, indent=2) + "\n")
    baseline_path = ROOT / "recipes" / f"{pid}.score.json"
    baseline = json.loads(baseline_path.read_text())
    improved = result["similarity"] > baseline["similarity"]
    if improved:
        if not (variant_dir / f"{pid}-pre-recolour.json").exists():
            (variant_dir / f"{pid}-pre-recolour.json").write_text(base_path.read_text())
            (variant_dir / f"{pid}-pre-recolour.png").write_bytes((ROOT / "recipes" / f"{pid}.png").read_bytes())
            (variant_dir / f"{pid}-pre-recolour.score.json").write_text(baseline_path.read_text())
        base_path.write_text(variant_path.read_text())
        (ROOT / "recipes" / f"{pid}.png").write_bytes(variant_png.read_bytes())
        baseline_path.write_text(variant_score_path.read_text())
    print(json.dumps({"id": pid, "baseline": baseline["similarity"], "candidate": result["similarity"], "promoted": improved, "ssim": result["ssim"], "delta_e": result["mean_delta_e"], "edge": result["edge_similarity"]}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("painting", choices=list(plan.META) + ["all"])
    parser.add_argument("--gain", type=float, default=0.38)
    args = parser.parse_args()
    for pid in (list(plan.META) if args.painting == "all" else [args.painting]):
        recolour(pid, args.gain)


if __name__ == "__main__":
    main()
