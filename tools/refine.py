#!/usr/bin/env python3
"""Residual-targeted replacement of the existing fine-detail stage.

The original is retained as a baseline. A candidate is promoted only when its
combined score improves; this makes repeated planning/render/score cycles safe.
"""
import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import plan
from score import score

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def render(recipe_path, png_path):
    subprocess.run(["node", str(ROOT / "tools" / "render.mjs"), str(recipe_path), str(png_path)], check=True, cwd=ROOT)


def refine(pid, seed=27183):
    base_path = ROOT / "recipes" / f"{pid}.json"
    recipe = json.loads(base_path.read_text())
    reference = np.asarray(Image.open(ROOT / "references" / f"{pid}.jpg").convert("RGB"), dtype=np.float32) / 255.0
    plan.REF_H, plan.REF_W = reference.shape[:2]
    plan.GX, plan.GY = np.gradient(np.dot(reference, [0.2126, 0.7152, 0.0722]))
    sigma = 0.55 if pid in ("mona-lisa", "girl-with-a-pearl-earring", "breakfast-at-tiffanys", "marilyn-1953") else 0.35
    field = plan.smooth(reference, sigma)
    plan.TANGENTS, plan.COHERENCE = plan.tensor_tangents(field, 0.6)

    prefix = copy.deepcopy(recipe)
    prefix["stages"][-1]["strokes"] = []
    prefix["strokeCount"] -= len(recipe["stages"][-1]["strokes"])
    variant_dir = ROOT / "recipes" / "variants"
    variant_dir.mkdir(exist_ok=True)
    prefix_path = variant_dir / f"{pid}-prefix.json"
    prefix_png = variant_dir / f"{pid}-prefix.png"
    prefix_path.write_text(json.dumps(prefix, separators=(",", ":")) + "\n")
    render(prefix_path, prefix_png)
    rendered = np.asarray(Image.open(prefix_png).convert("RGB"), dtype=np.float32) / 255.0
    weight = plan.residual_weight(reference, rendered)

    rng = np.random.default_rng(seed + sum(ord(c) for c in pid))
    count = len(recipe["stages"][-1]["strokes"])
    details = []
    for _ in range(count):
        stroke = plan.make_stroke(pid, field, weight, (1.3, 4.8), (0.7, 1.55), (0.76, 0.95), rng, True, True)
        stroke["stage"] = "detail"
        details.append(stroke)
    recipe["stages"][-1]["strokes"] = details
    recipe["planner"] += "; residual-targeted final detail replacement"
    recipe["refinementSeed"] = seed
    variant_path = variant_dir / f"{pid}-residual.json"
    variant_png = variant_dir / f"{pid}-residual.png"
    variant_score = variant_dir / f"{pid}-residual.score.json"
    variant_path.write_text(json.dumps(recipe, separators=(",", ":")) + "\n")
    render(variant_path, variant_png)
    result = score(ROOT / "references" / f"{pid}.jpg", variant_png)
    variant_score.write_text(json.dumps(result, indent=2) + "\n")

    baseline_path = ROOT / "recipes" / f"{pid}.score.json"
    baseline = json.loads(baseline_path.read_text())
    improved = result["similarity"] > baseline["similarity"]
    if improved:
        (variant_dir / f"{pid}-base.json").write_text(base_path.read_text())
        (variant_dir / f"{pid}-base.png").write_bytes((ROOT / "recipes" / f"{pid}.png").read_bytes())
        (variant_dir / f"{pid}-base.score.json").write_text(baseline_path.read_text())
        base_path.write_text(variant_path.read_text())
        (ROOT / "recipes" / f"{pid}.png").write_bytes(variant_png.read_bytes())
        baseline_path.write_text(variant_score.read_text())
    prefix_path.unlink()
    prefix_png.unlink()
    print(json.dumps({"id": pid, "baseline": baseline["similarity"], "candidate": result["similarity"], "promoted": improved, "candidate_metrics": result}))
    return improved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("painting", choices=list(plan.META) + ["all"])
    args = parser.parse_args()
    for pid in (list(plan.META) if args.painting == "all" else [args.painting]):
        refine(pid)


if __name__ == "__main__":
    main()
