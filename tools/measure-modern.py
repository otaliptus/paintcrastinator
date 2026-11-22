#!/usr/bin/env python3
"""Measure Modern colour budgets and ship the smallest acceptable recipe."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from score import score

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
IDS = ["sunflowers", "the-snail", "mondrian-1930"]
BUDGETS = {
    "sunflowers": [2500, 5000],
    "the-snail": [500, 1000, 1500, 2500, 5000],
    "mondrian-1930": [500, 1000, 1500, 2500, 5000],
}


def run(args):
    result = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(map(str, args))}\n{result.stdout[-1200:]}")


def preserve(path):
    backup = path.with_name(path.name + ".bak-t3")
    if path.exists() and not backup.exists():
        shutil.copyfile(path, backup)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paintings", nargs="*", choices=IDS, help="Modern colour studies to measure; default is all three")
    args = parser.parse_args()
    variants = ROOT / "recipes" / "variants"
    variants.mkdir(exist_ok=True)
    result_path = ROOT / "verification" / "modern-budget-scores.json"
    results = json.loads(result_path.read_text()) if result_path.exists() else {}
    results = {pid: results[pid] for pid in IDS if pid in results}
    preserve(result_path)
    for pid in args.paintings or IDS:
        entry = {"scores": {}}
        for budget in BUDGETS[pid]:
            recipe_path = variants / f"{pid}-{budget}.json"
            png_path = variants / f"{pid}-{budget}.png"
            score_path = variants / f"{pid}-{budget}.score.json"
            for path in (recipe_path, png_path, score_path):
                preserve(path)
            run([PYTHON, str(ROOT / "tools" / "plan.py"), pid, "--strokes", str(budget), "--output", str(recipe_path)])
            run(["node", str(ROOT / "tools" / "render.mjs"), str(recipe_path), str(png_path)])
            measured = score(ROOT / "references" / f"{pid}.jpg", png_path)
            score_path.write_text(json.dumps(measured, indent=2) + "\n")
            entry["scores"][str(budget)] = measured["similarity"]
            print(f"{pid} {budget}: {measured['similarity']:.3f}", flush=True)
        selected = next(budget for budget in BUDGETS[pid] if entry["scores"][str(budget)] >= entry["scores"]["5000"] - 2.0)
        entry["selected"] = selected
        results[pid] = entry
        for path in (ROOT / "recipes" / f"{pid}.json", ROOT / "recipes" / f"{pid}.png", ROOT / "recipes" / f"{pid}.score.json"):
            preserve(path)
        shutil.copyfile(variants / f"{pid}-{selected}.json", ROOT / "recipes" / f"{pid}.json")
        shutil.copyfile(variants / f"{pid}-{selected}.png", ROOT / "recipes" / f"{pid}.png")
        shutil.copyfile(variants / f"{pid}-{selected}.score.json", ROOT / "recipes" / f"{pid}.score.json")
        result_path.write_text(json.dumps(results, indent=2) + "\n")
        print(f"{pid} selected: {selected}", flush=True)


if __name__ == "__main__":
    main()
