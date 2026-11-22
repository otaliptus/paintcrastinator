#!/usr/bin/env python3
"""Update an existing Modern recipe without disturbing the Start here shelf."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("painting", choices=["the-snail", "mondrian-1930", "sunflowers"])
    args = parser.parse_args()
    pid = args.painting
    recipe_path = ROOT / "recipes" / f"{pid}.json"
    score_path = ROOT / "recipes" / f"{pid}.score.json"
    recipe = json.loads(recipe_path.read_text())
    scores = json.loads(score_path.read_text())
    actual = sum(len(stage["strokes"]) for stage in recipe["stages"])
    assert actual == recipe["strokeCount"]
    recipe["scores"] = scores
    recipe_path.write_text(json.dumps(recipe, separators=(",", ":")) + "\n")

    manifest_path = ROOT / "recipes" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    index = next(i for i, item in enumerate(manifest) if item["id"] == pid)
    old = manifest[index]
    for key in ["title", "artist", "year", "width", "height", "strokeCount", "credit"]:
        if key in recipe:
            old[key] = recipe[key]
    old["scores"] = scores
    old["reference"] = recipe["reference"].removeprefix("../")
    if recipe.get("description"):
        old["description"] = recipe["description"]
    manifest[index] = old
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    report_path = ROOT / "REPORT.md"
    report = report_path.read_text()
    row = f"| {recipe['title']} | {actual:,} | {scores['ssim']:.5f} | {scores['mean_delta_e']:.4f} | {scores['edge_similarity']:.5f} | **{scores['similarity']:.3f}** |"
    report, replacements = re.subn(rf"^\| {re.escape(recipe['title'])} \| [\d,]+ \| .*$", row, report, count=1, flags=re.MULTILINE)
    assert replacements == 1
    if pid == "the-snail":
        note = "\nTask 4 rebuilt The Snail as a 2,000-stroke cut-paper study: fourteen Lab colour clusters, one underlying white sheet, median flat colours, straight polygon-scan fills and inset 5–8 px edge strokes. Tiny fringe components were removed so the orange cutouts stay clean. The accepted render scores **88.757** and has straight sheet edges, sharp corners and a square black centre.\n"
        report = report.replace("\n<!-- START_HERE_REPORT -->", note + "\n<!-- START_HERE_REPORT -->")
    report_path.write_text(report)
    print(json.dumps({"id": pid, "strokes": actual, "similarity": scores["similarity"], "manifestRecipes": len(manifest)}))


if __name__ == "__main__":
    main()
