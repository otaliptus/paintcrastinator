# Painting Cookbook — build brief for Kimi

You are building **Painting Cookbook**: a small browser app with a "recipe" for each of five famous
public-domain paintings. Each recipe is a list of about 5,000 brush strokes that, painted in order with
a simple soft round brush, recreates the painting as closely as possible. People open a recipe and
either watch it being painted or paint it themselves, stroke by stroke, following the guide.

The project folder is `/home/node/.openclaw/workspace/painting-cookbook`. The reference paintings
are in `references/` (mona-lisa, girl-with-a-pearl-earring, starry-night, great-wave,
van-gogh-self-portrait; JPEG, 960 px wide). Work only inside this folder.

## 1. The brush engine (do this first)
- `app/brush.js`: one plain-JS module that paints a stroke onto a 2D canvas context. A stroke is
  `{ "p": [x0,y0, x1,y1, ...], "c": "#rrggbb", "s": size, "o": opacity }`, coordinates in the
  painting's own pixel space (the reference size). Soft round brush: stamps along the path with a
  radial falloff, spacing about a quarter of the size, so short and long strokes both look painted.
- Everything that renders strokes (the app, the offline renderer, the replay) must use this same
  file, so what you score offline is exactly what people see.

## 2. The offline pipeline (Kimi discovers the recipes)
- `tools/render.mjs`: renders a recipe JSON to a PNG with headless Chromium and `app/brush.js`.
  Playwright is at `/app/node_modules/playwright-core` (Chromium is already installed); import it
  by that absolute path.
- `tools/score.py`: compares a render with its reference and prints a JSON score: SSIM on grayscale
  at reduced size, mean colour difference (CIE Lab delta E) on a downscaled grid, and an edge
  similarity term. Use the Python at `/home/node/.openclaw/venv/bin/python` (numpy, pillow and
  scikit-image are installed).
- `tools/plan.py` (or several planners if you like): analyses a reference with code and writes
  `recipes/<id>.json`. Paint like an artist, in four stages, and record the stage of each stroke:
  1. **Blocking in**: a few hundred huge, rough strokes for the big shapes and the background.
  2. **Form and color**: medium strokes that build form and the main colour areas.
  3. **Refinement**: smaller strokes for edges and transitions.
  4. **Fine details**: tiny strokes for eyes, mouths, hands, hair edges, highlights and the most
     distinctive marks of each painting (Starry Night's swirls, the Great Wave's foam claws,
     Van Gogh's directional brushwork, the pearl's highlight, Mona Lisa's soft sfumato).
  Strokes follow the direction of the forms (use image gradients or structure tensors), never a
  regular grid. Stroke budget per painting: 4,500 to 5,500.
- The loop: plan → render → score → look at the render next to the reference (you can view
  images) → change the planner → repeat. Keep the best version of each recipe. Keep going until
  further changes stop improving both the score and how recognisable the painting looks to you.
- Save for each painting: `recipes/<id>.json` (with title, artist, year, width, height, and the
  strokes grouped by stage), `recipes/<id>.png` (the final render) and its score.

## 3. The app
Plain HTML, CSS and JS, no frameworks, no external assets, no image-generation services.
- **Library** (`app/index.html`): a grid of the five paintings showing the finished stroke render
  (not the photo), title, artist, stroke count and similarity score.
- **Recipe page**: a large canvas on the left with the painting's proportions, starting blank; on
  the right a small reference panel with the painting, the current stage label and progress.
  - **Watch** mode: replays the recipe stroke by stroke, with play/pause, speed control (from
    "one stroke at a time" to "whole painting in about 20 seconds") and a stage scrubber.
  - **Paint along** mode: shows the next stroke as a faint ghost guide (path, colour swatch, size).
    The person paints it with mouse, pen or touch; the app snaps their colour and size to the
    recipe's, records their stroke, then moves to the next one. A "skip ahead" button lets them
    auto-paint the rest of the current stage. Show a live similarity score of their canvas.
  - A top bar with the title "Painting Cookbook" and a live stroke counter.
- Never draw the reference photo onto the painting canvas (no drawImage of the reference,
  putImageData of its pixels, CSS background, filter or mask). The reference appears only in the
  reference panel and the library grid's "original" toggle.
- Works on a phone as well as a desktop.

## Done means
- `cd painting-cookbook && python3 -m http.server 8080` serves the app at
  `http://localhost:8080/app/`, with no console errors (check with headless Chromium).
- All five recipes exist, each within the stroke budget, with renders and scores in `REPORT.md`
  (table of the scores, what you tried, and what made the biggest difference).
- Do not deploy or push anywhere.
