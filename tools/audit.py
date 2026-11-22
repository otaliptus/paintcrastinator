#!/usr/bin/env python3
"""Validate the shipped references, vector recipes, renders and score metadata."""
import json
import math
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MASTERWORK_IDS = ["mona-lisa", "girl-with-a-pearl-earring", "starry-night", "great-wave", "van-gogh-self-portrait"]
ICON_IDS = ["countach", "breakfast-at-tiffanys", "marilyn-1953", "the-scream", "blue-marble"]
MODERN_IDS = ["sunflowers", "the-snail", "mondrian-1930"]
PHOTO_IDS = {"countach", "breakfast-at-tiffanys", "marilyn-1953", "blue-marble"}
FLAT_IDS = {"the-snail", "mondrian-1930"}
IDS = MASTERWORK_IDS + ICON_IDS + MODERN_IDS
SIZES = {"mona-lisa": (960, 1431), "girl-with-a-pearl-earring": (960, 1137), "starry-night": (960, 760), "great-wave": (960, 645), "van-gogh-self-portrait": (960, 1213), "countach": (960, 508), "breakfast-at-tiffanys": (960, 1201), "marilyn-1953": (960, 1048), "the-scream": (960, 1191), "blue-marble": (960, 961), "sunflowers": (960, 1221), "the-snail": (960, 970), "mondrian-1930": (960, 973)}
manifest = json.loads((ROOT / "recipes" / "manifest.json").read_text())
assert {entry["id"] for entry in manifest} == set(IDS)
summary = []
for pid in IDS:
    assert Image.open(ROOT / "references" / f"{pid}.jpg").size == SIZES[pid]
    assert Image.open(ROOT / "recipes" / f"{pid}.png").size == SIZES[pid]
    recipe = json.loads((ROOT / "recipes" / f"{pid}.json").read_text())
    assert (recipe["width"], recipe["height"]) == SIZES[pid]
    assert [stage["id"] for stage in recipe["stages"]] == ["blocking", "form", "refinement", "detail"]
    count = 0
    stage_counts = []
    for stage in recipe["stages"]:
        stage_counts.append(len(stage["strokes"]))
        for stroke in stage["strokes"]:
            # A single point is a valid round dab; longer paths are polylines.
            assert len(stroke["p"]) >= 2 and len(stroke["p"]) % 2 == 0
            assert all(isinstance(value, (int, float)) and math.isfinite(value) for value in stroke["p"])
            assert isinstance(stroke["c"], str) and len(stroke["c"]) == 7 and stroke["c"][0] == "#"
            int(stroke["c"][1:], 16)
            assert 0.25 <= stroke["s"] <= 500
            assert 0 < stroke["o"] <= 1
            assert stroke["stage"] == stage["id"]
        count += len(stage["strokes"])
    assert count == recipe["strokeCount"]
    if pid in MASTERWORK_IDS:
        assert 4000 <= count <= 6000
        assert stage_counts[0] <= 450 and stage_counts[-1] >= 500
    elif pid in PHOTO_IDS:
        assert 1500 <= count <= 5000 and recipe["profile"] == "photo"
        assert recipe["credit"]["author"] and recipe["credit"]["licence"] and recipe["credit"]["url"].startswith("https://commons.wikimedia.org/")
    elif pid in FLAT_IDS:
        assert 500 <= count <= 5000 and recipe["profile"] == "flat"
        assert all(len(stroke["p"]) == 4 for stage in recipe["stages"] for stroke in stage["strokes"])
        assert all(stroke["o"] == 1 for stage in recipe["stages"] for stroke in stage["strokes"])
        assert recipe["credit"]["author"] and recipe["credit"]["licence"]
    elif pid == "sunflowers":
        assert 2500 <= count <= 5000 and recipe["profile"] == "painterly"
        assert recipe["credit"]["licence"] == "Public domain"
    else:
        assert 1500 <= count <= 5000 and recipe.get("profile") != "photo"
        assert recipe["credit"]["licence"] == "Public domain"
    scores = json.loads((ROOT / "recipes" / f"{pid}.score.json").read_text())
    for key in ["ssim", "mean_delta_e", "edge_similarity", "similarity"]:
        assert scores[key] == recipe["scores"][key]
    assert next(entry for entry in manifest if entry["id"] == pid)["scores"] == scores
    if pid in ICON_IDS or pid in MODERN_IDS:
        assert next(entry for entry in manifest if entry["id"] == pid)["credit"] == recipe["credit"]
    if pid == "the-snail":
        assert recipe["credit"]["note"] == "Public domain in the EU; in copyright in some other countries."
    summary.append({"id": pid, "dimensions": SIZES[pid], "stages": stage_counts, "strokes": count, "similarity": scores["similarity"]})

brush = (ROOT / "app" / "brush.js").read_text()
assert "drawImage" in brush and "createRadialGradient" in brush and "spacing = Math.max(0.25, size * 0.25)" in brush
assert "reference" not in brush.lower()
print(json.dumps({"ok": True, "paintings": summary, "shared_brush_reference_free": True}, indent=2))
