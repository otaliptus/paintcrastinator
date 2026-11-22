#!/usr/bin/env python3
"""Publish one completed Start here recipe to the manifest, report and credits."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = ["lesson-sky", "lesson-sphere", "lesson-hills", "impression-sunrise", "nocturne-battersea", "sudden-shower", "composition-viii", "basket-of-apples"]


def write_report(manifest, budget_data):
    completed = [next(item for item in manifest if item["id"] == pid) for pid in START if any(item["id"] == pid for item in manifest)]
    lines = [
        "<!-- START_HERE_REPORT -->",
        "## Start here — short paint-along recipes",
        "",
        "These recipes are ordered from easiest to hardest and selected by visual recognisability at a small stroke count, not by the earlier 2.0-point budget rule. Estimated Paint Along time uses about four seconds per stroke.",
        "",
        "| Recipe | Strokes | Paint Along | Composite / 100 |",
        "|---|---:|---:|---:|",
    ]
    for item in completed:
        minutes = max(1, round(item["strokeCount"] * 4 / 60))
        lines.append(f"| {item['title']} | {item['strokeCount']} | ≈ {minutes} min | **{item['scores']['similarity']:.3f}** |")
    if budget_data:
        lines += ["", "### Budget trials", "", "| Recipe | Trial strokes → composite | Selected |", "|---|---|---:|"]
        for item in completed:
            record = budget_data.get(item["id"], {})
            trials = record.get("candidates", [])
            cells = "; ".join(f"{trial['strokes']} → {trial['similarity']:.3f}" for trial in trials)
            lines.append(f"| {item['title']} | {cells} | **{item['strokeCount']}** |")
    lines += ["", "The generated lesson references are original Pillow/NumPy images dedicated CC0. The five painting references use their source credits in the manifest and CREDITS.md.", ""]
    path = ROOT / "REPORT.md"
    base = path.read_text().split("<!-- START_HERE_REPORT -->")[0].rstrip()
    path.write_text(base + "\n\n" + "\n".join(lines))


def write_credits(manifest):
    lines = ["<!-- START_HERE_CREDITS -->", "## Start here references", ""]
    for pid in START:
        entry = next((item for item in manifest if item["id"] == pid), None)
        if not entry:
            continue
        credit = entry["credit"]
        if pid.startswith("lesson-"):
            lines.append(f"- **_{entry['title']}_:** Generated for Painting Cookbook, CC0. Reference drawn in Python with Pillow/NumPy at 960 px wide; [CC0 dedication](https://creativecommons.org/publicdomain/zero/1.0/).")
        else:
            lines.append(f"- **_{entry['title']}_ ({entry['year']}):** {entry['artist']}, {credit['licence']}, [via Wikimedia Commons]({credit['url']}).")
    path = ROOT / "CREDITS.md"
    base = path.read_text().split("<!-- START_HERE_CREDITS -->")[0].rstrip()
    path.write_text(base + "\n\n" + "\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("painting", choices=START)
    args = parser.parse_args()
    pid = args.painting
    recipe_path = ROOT / "recipes" / f"{pid}.json"
    score_path = ROOT / "recipes" / f"{pid}.score.json"
    recipe = json.loads(recipe_path.read_text())
    scores = json.loads(score_path.read_text())
    actual = sum(len(stage["strokes"]) for stage in recipe["stages"])
    assert actual == recipe["strokeCount"] == scores.get("strokeCount", actual)
    recipe["scores"] = scores
    recipe_path.write_text(json.dumps(recipe, separators=(",", ":")) + "\n")
    entry = {key: recipe[key] for key in ["id", "title", "artist", "year", "width", "height", "strokeCount", "scores", "credit", "description"]}
    entry["reference"] = recipe["reference"].removeprefix("../")
    if recipe.get("lessonTip"):
        entry["lessonTip"] = recipe["lessonTip"]
    manifest_path = ROOT / "recipes" / "manifest.json"
    old = json.loads(manifest_path.read_text())
    by_id = {item["id"]: item for item in old if item["id"] not in START}
    by_id[pid] = entry
    start_entries = []
    for start_id in START:
        if start_id == pid:
            start_entries.append(entry)
        else:
            previous = next((item for item in old if item["id"] == start_id), None)
            if previous:
                start_entries.append(previous)
    ordered = start_entries + [item for item in old if item["id"] not in START]
    manifest_path.write_text(json.dumps(ordered, indent=2) + "\n")
    budget_path = ROOT / "verification" / "start-budget-scores.json"
    budget_data = json.loads(budget_path.read_text()) if budget_path.exists() else {}
    write_report(ordered, budget_data)
    write_credits(ordered)
    print(json.dumps({"id": pid, "strokes": actual, "similarity": scores["similarity"], "manifestRecipes": len(ordered)}))


if __name__ == "__main__":
    main()
