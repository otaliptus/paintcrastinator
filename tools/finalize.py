#!/usr/bin/env python3
"""Publish score metadata for the static library and regenerate REPORT.md."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTERWORK_IDS = ["mona-lisa", "girl-with-a-pearl-earring", "starry-night", "great-wave", "van-gogh-self-portrait"]
ICON_IDS = ["countach", "breakfast-at-tiffanys", "marilyn-1953", "the-scream", "blue-marble"]
IDS = MASTERWORK_IDS + ICON_IDS
manifest = []
rows = []
for pid in IDS:
    recipe_path = ROOT / "recipes" / f"{pid}.json"
    score_path = ROOT / "recipes" / f"{pid}.score.json"
    recipe = json.loads(recipe_path.read_text())
    scores = json.loads(score_path.read_text())
    recipe["scores"] = scores
    recipe_path.write_text(json.dumps(recipe, separators=(",", ":")) + "\n")
    entry = {key: recipe[key] for key in ["id", "title", "artist", "year", "width", "height", "strokeCount", "scores"]}
    if "credit" in recipe:
        entry["credit"] = recipe["credit"]
    manifest.append(entry)
    rows.append((recipe["title"], recipe["strokeCount"], scores))
(ROOT / "recipes" / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

lines = [
    "# Painting Cookbook — Score Report",
    "",
    "Every score is computed from the stored reference and the PNG emitted by the same `app/brush.js` engine used by the app. Renders contain only canvas-ground plus recipe strokes; no reference pixels are painted.",
    "",
    "| Painting | Strokes | SSIM ↑ | Mean CIE ΔE2000 ↓ | Edge similarity ↑ | Composite / 100 ↑ |",
    "|---|---:|---:|---:|---:|---:|",
]
for title, count, scores in rows:
    lines.append(f"| {title} | {count:,} | {scores['ssim']:.5f} | {scores['mean_delta_e']:.4f} | {scores['edge_similarity']:.5f} | **{scores['similarity']:.3f}** |")

budget_path = ROOT / "verification" / "photo-budget-scores.json"
if budget_path.exists():
    budgets = json.loads(budget_path.read_text())
    lines += [
        "",
        "## Icons — stroke-count selection",
        "",
        "Each Icon was planned, rendered and scored independently at all three budgets. The shipped recipe is the smallest measured count within 2.0 composite points of its 5,000-stroke result, with a floor of 1,500 strokes.",
        "",
        "| Painting | 1,500 strokes | 2,500 strokes | 5,000 strokes | Shipped | Δ from 5,000 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for pid in ICON_IDS:
        result = budgets[pid]
        values = result["scores"]
        selected = result["selected"]
        delta = values[str(selected)] - values["5000"]
        title = next(entry["title"] for entry in manifest if entry["id"] == pid)
        lines.append(f"| {title} | {values['1500']:.3f} | {values['2500']:.3f} | {values['5000']:.3f} | **{selected:,}** | {delta:+.3f} |")
initial = {"Mona Lisa": 74.413, "Girl with a Pearl Earring": 75.200, "The Starry Night": 52.886, "The Great Wave off Kanagawa": 62.995, "Self-Portrait": 56.791}
lines += [
    "",
    "## What changed, and what helped",
    "",
    "The deterministic planner progressively unblurs the colour field across four stages, samples positions by colour-change and edge importance, and steers marks with structure-tensor tangents plus painting-specific weak-structure flow. Broad-to-fine multiscale blocking made the largest difference to recognisability; structure-following marks were especially important for Starry Night's currents and Great Wave's nested contours.",
    "",
    "After viewing every reference/render pair, a residual-targeted replacement of the final detail stage was tested on all five. It improved Vermeer slightly and was rejected elsewhere. A conservative residual colour-feedback pass then improved four composite scores (all except Mona Lisa) and was retained, mainly through stronger edge agreement. A smaller second feedback pass lowered every composite and was rejected, so iteration stopped and the best five recipes were frozen and rendered again through the shared brush.",
    "",
    "| Painting | First verified composite | Final composite | Change |",
    "|---|---:|---:|---:|",
]
for title, count, scores in rows:
    if title not in initial:
        continue
    lines.append(f"| {title} | {initial[title]:.3f} | {scores['similarity']:.3f} | {scores['similarity'] - initial[title]:+.3f} |")
lines += [
    "",
    "The textured works remain deliberately painterly approximations: their uncorrelated high-frequency canvas texture limits SSIM even when large forms and colours are recognisable. The score comparison and visual check therefore both informed candidate rejection.",
    "",
    "## Method",
    "",
    "- **SSIM:** grayscale, longest side reduced to 384 px.",
    "- **CIE Lab delta E:** CIEDE2000 mean on RGB colours, longest side reduced to 160 px; lower is better.",
    "- **Edge similarity:** overlap of reduced-resolution Sobel magnitude fields; higher is better.",
    "- **Composite:** 55% SSIM + 30% colour similarity + 15% edge similarity, reported on a 0–100 scale. Colour similarity is `clamp(1 - meanΔE/50, 0, 1)`. This is a project comparison index, not an external benchmark.",
    "",
    "Scores are rounded only for presentation. The full method and unrounded-input results are stored beside each recipe in `recipes/<id>.score.json`.",
]
(ROOT / "REPORT.md").write_text("\n".join(lines) + "\n")
print(json.dumps(manifest, indent=2))
