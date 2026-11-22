# Painting Cookbook

Thirteen studies, each recreated by **500–5,000 soft-round brush strokes** in four stages: five masterworks, five Icons, and three Modern colour works by Van Gogh, Matisse and Mondrian. The static app uses vanilla JavaScript and Canvas 2D; planning and scoring use Python.

## Run the app

Serve the parent directory (the app loads sibling `app/` and `recipes/` paths):

```bash
cd /home/node/.openclaw/workspace/painting-cookbook
python3 -m http.server 4173
```

Open <http://localhost:4173/app/>.

- The library thumbnails are **recipe renders**, not reference photos. “View original” explicitly swaps a thumbnail to the reference and back.
- Every recipe page starts blank. **Watch** builds the painting through the recipe; a per-recipe default speed completes in about 20 seconds. Play/pause, speed, continuous scrubbing, and four exact stage jumps are available.
- **Paint Along** starts from blank. Drag or touch along each dashed ghost path. The gesture is yours; the recipe supplies colour, size and opacity. Every completed pointer stroke advances the counter. “Finish this stage” auto-paints the rest of the current stage. Live colour match compares reduced-resolution RGB against the reference.
- The original image is used only in the reference panel, explicit library toggle, and offscreen live-score calculation. It is never painted onto either visible painting canvas.

## Offline pipeline

The bundled Playwright Core is imported from `/app/node_modules/playwright-core`. Its Chromium runtime must be available. The planning/scoring commands use this environment's `/home/node/.openclaw/venv/bin/python` with NumPy, SciPy, scikit-image, Pillow and OpenCV.

```bash
# Discover a four-stage, deterministic 5,000-stroke vector recipe.
/home/node/.openclaw/venv/bin/python tools/plan.py mona-lisa
/home/node/.openclaw/venv/bin/python tools/plan.py all
# Scale all four stages to a smaller photographic budget.
/home/node/.openclaw/venv/bin/python tools/plan.py countach --strokes 1500

# Chromium rendering through app/brush.js — no Python raster painter.
node tools/render.mjs recipes/mona-lisa.json recipes/mona-lisa.png
node tools/render.mjs --all

# Reduced-resolution structural, CIE Lab and edge scoring.
/home/node/.openclaw/venv/bin/python tools/score.py \
  references/mona-lisa.jpg recipes/mona-lisa.png \
  --output recipes/mona-lisa.score.json

# Independently measure all Modern colour budgets and select the smallest within 2.0 points of 5,000.
/home/node/.openclaw/venv/bin/python tools/measure-modern.py

# Write the library manifest and REPORT.md.
/home/node/.openclaw/venv/bin/python tools/finalize.py
```

Optional measured improvement passes save candidates under `recipes/variants/` and promote only a higher composite score:

```bash
/home/node/.openclaw/venv/bin/python tools/refine.py all
/home/node/.openclaw/venv/bin/python tools/recolor.py all
```

## Recipe format

```json
{
  "id": "mona-lisa",
  "title": "Mona Lisa",
  "artist": "Leonardo da Vinci",
  "year": "c. 1503–1519",
  "width": 960,
  "height": 1431,
  "ground": "#ffffff",
  "stages": [
    {
      "id": "blocking",
      "label": "Blocking in",
      "strokes": [
        {"p": [20, 30, 70, 55, 120, 80], "c": "#6e6242", "s": 90, "o": 0.85, "stage": "blocking"}
      ]
    }
  ]
}
```

`p` is any even-length sequence of canvas x/y coordinates, permitting straight, curved and freehand paths. `s` is brush diameter in canvas pixels, `o` is 0–1 opacity, and `c` is six-digit RGB hex. The four stage IDs are `blocking`, `form`, `refinement`, and `detail`. `flattenStages()` preserves their order. Each finished recipe also carries its measured `scores` object.

## Shared brush contract

`app/brush.js` is imported by:

1. `tools/render-page.html`, driven by `tools/render.mjs` for offline PNGs;
2. Watch replay in `app/recipe.js`;
3. Paint Along in `app/recipe.js`.

The engine stamps a tinted radial-alpha falloff at quarter-diameter spacing along every polyline segment. A bounded LRU stamp cache makes replay practical. There is no renderer-only drawing shortcut and no reference-image raster input.

## Planner

`tools/plan.py` uses deterministic randomness, progressively less blurred multiscale colour fields, structure-tensor tangent/coherence estimates and grid-free importance sampling. Painting-specific weak-structure flow adds circular wind to Starry Night, curved wave contours to Great Wave, sky bands and straight bridge diagonals to The Scream, tangent-following cloud swirls to Blue Marble, and radial petal impasto to Sunflowers. The flat profile used by The Snail and Mondrian segments CIE Lab colours into connected regions, assigns each region's exact mean colour, lays straight mask-clipped fills and sharpens contours with straight strokes—without texture noise. Their 500-stroke coverage/finish core stays fixed in larger candidates, whose extra marks are blocking underpaint; this makes the budget sweep a direct test of redundant coverage. Audrey Hepburn's figure receives 70% of refinement/detail strokes while the patterned screen becomes sparse, soft pale blocks; Blue Marble uses a brightness-derived disc mask and path constraints to keep space black. Later short marks respond to edge energy. Residual passes use the shared-engine render as feedback; saved baselines prevent a worse candidate from replacing a better recipe.

## Scores

See [REPORT.md](REPORT.md). Each recipe has a sibling `.score.json` containing SSIM, mean CIEDE2000, edge overlap and the 0–100 composite. These are reduced-resolution similarity measurements, not claims of exact reproduction.

## App verification

With the local server running:

```bash
node tools/test-app.mjs
```

The Playwright suite checks three shelves and thirteen cards, Modern colour ordering and a sub-1,500-stroke counter, original toggling, variable-budget replay/pause, exact stage boundaries, full scrubbing, pointer painting and live score, undo/restart, every recipe/reference, linked credits and copyright notes, mobile layout and touch painting. It fails on any browser console error or uncaught page error. Desktop/mobile screenshots are written to `verification/`, including the required library and The Scream desktop views.

## Icons

Five Icon studies use independently measured 1,500, 2,500 and 5,000-stroke candidates; REPORT.md records every composite and the selected budget.
The Countach photograph is credited by photographer, CC BY-SA 4.0 licence and Wikimedia source. The two publicity photographs, The Scream and the NASA/Apollo 17 photograph carry public-domain credits and sources in the library, recipe pages and CREDITS.md.
Use `tools/measure-photos.py` to rerun the Icons sweep and `tools/measure-modern.py` for the new shelf, then `tools/finalize.py` to refresh score metadata and the manifest. `tools/contact-modern.py` writes the three-pair reference/render contact sheet.
