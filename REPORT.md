# Painting Cookbook — Score Report

Every score is computed from the stored reference and the PNG emitted by the same `app/brush.js` engine used by the app. Renders contain only canvas-ground plus recipe strokes; no reference pixels are painted.

| Painting | Strokes | SSIM ↑ | Mean CIE ΔE2000 ↓ | Edge similarity ↑ | Composite / 100 ↑ |
|---|---:|---:|---:|---:|---:|
| Mona Lisa | 5,000 | 0.74131 | 2.4708 | 0.66657 | **79.288** |
| Girl with a Pearl Earring | 5,000 | 0.77775 | 1.9136 | 0.71904 | **82.414** |
| The Starry Night | 5,000 | 0.44258 | 4.5279 | 0.55159 | **59.899** |
| The Great Wave off Kanagawa | 5,000 | 0.61823 | 3.7490 | 0.62178 | **71.080** |
| Self-Portrait | 5,000 | 0.48924 | 5.4425 | 0.54920 | **61.881** |
| Lamborghini Countach LP5000 S | 5,000 | 0.53176 | 3.8798 | 0.64136 | **66.539** |
| Audrey Hepburn, Breakfast at Tiffany's | 2,500 | 0.37158 | 3.7158 | 0.36177 | **53.634** |
| Marilyn Monroe | 5,000 | 0.79763 | 1.6956 | 0.71613 | **83.594** |
| The Scream | 5,000 | 0.69764 | 3.0563 | 0.61935 | **75.827** |
| The Blue Marble | 5,000 | 0.55410 | 2.8538 | 0.63026 | **68.217** |
| Sunflowers | 5,000 | 0.65467 | 2.5097 | 0.63623 | **74.044** |
| The Snail | 2,000 | 0.90918 | 2.2567 | 0.67372 | **88.757** |
| Composition with Red, Blue and Yellow | 500 | 0.80781 | 4.6569 | 0.37060 | **77.194** |
| Almond Blossom | 2,800 | 0.51663 | 5.1018 | 0.49198 | **62.734** |
| Woman with a Parasol | 2,400 | 0.48400 | 5.5820 | 0.48418 | **60.534** |
| Wanderer above the Sea of Fog | 1,800 | 0.64630 | 3.8929 | 0.46364 | **70.165** |
| Sunset over a Still Sea | 20 | 0.93770 | 2.0841 | 0.39498 | **86.248** |
| Orange Ball on a Table | 48 | 0.87977 | 2.8026 | 0.34544 | **81.887** |
| Three Hills in Morning Haze | 31 | 0.85205 | 2.7578 | 0.02661 | **75.607** |

## Icons — stroke-count selection

Each Icon was planned, rendered and scored independently at all three budgets. The shipped recipe is the smallest measured count within 2.0 composite points of its 5,000-stroke result, with a floor of 1,500 strokes.

| Painting | 1,500 strokes | 2,500 strokes | 5,000 strokes | Shipped | Δ from 5,000 |
|---|---:|---:|---:|---:|---:|
| Lamborghini Countach LP5000 S | 47.695 | 51.445 | 56.714 | **5,000** | +0.000 |
| Audrey Hepburn, Breakfast at Tiffany's | 51.716 | 53.634 | 55.337 | **2,500** | -1.703 |
| Marilyn Monroe | 63.387 | 67.144 | 74.596 | **5,000** | +0.000 |
| The Scream | 51.160 | 60.814 | 67.904 | **5,000** | +0.000 |
| The Blue Marble | 51.616 | 54.951 | 59.422 | **5,000** | +0.000 |

## Modern colour — stroke-count selection

Each new work was planned, rendered and scored independently at every listed budget. The shipped recipe is the smallest within 2.0 composite points of its 5,000-stroke result: a 2,500-stroke floor for painterly Sunflowers and a 500-stroke floor for the flat profile. Flat candidates keep one identical 500-stroke coverage/finish core; larger budgets add only blocking underpaint, directly testing whether redundant coverage improves the result.

| Painting | 500 strokes | 1,000 strokes | 1,500 strokes | 2,500 strokes | 5,000 strokes | Shipped | Δ from 5,000 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Sunflowers | — | — | — | 60.391 | 66.258 | **5,000** | +0.000 |
| The Snail | 74.415 | 74.132 | 74.102 | 74.083 | 74.047 | **500** | +0.368 |
| Composition with Red, Blue and Yellow | 77.194 | 77.542 | 77.580 | 77.586 | 77.559 | **500** | -0.365 |

## What changed, and what helped

The deterministic planner progressively unblurs the colour field across four stages, samples positions by colour-change and edge importance, and steers marks with structure-tensor tangents plus painting-specific weak-structure flow. Broad-to-fine multiscale blocking made the largest difference to recognisability; structure-following marks were especially important for Starry Night's currents and Great Wave's nested contours.

After viewing every reference/render pair, a residual-targeted replacement of the final detail stage was tested on all five. It improved Vermeer slightly and was rejected elsewhere. A conservative residual colour-feedback pass then improved four composite scores (all except Mona Lisa) and was retained, mainly through stronger edge agreement. A smaller second feedback pass lowered every composite and was rejected, so iteration stopped and the best five recipes were frozen and rendered again through the shared brush.

| Painting | First verified composite | Final composite | Change |
|---|---:|---:|---:|
| Mona Lisa | 74.413 | 79.288 | +4.875 |
| Girl with a Pearl Earring | 75.200 | 82.414 | +7.214 |
| The Starry Night | 52.886 | 59.899 | +7.013 |
| The Great Wave off Kanagawa | 62.995 | 71.080 | +8.085 |
| Self-Portrait | 56.791 | 61.881 | +5.090 |

The textured works remain deliberately painterly approximations: their uncorrelated high-frequency canvas texture limits SSIM even when large forms and colours are recognisable. The score comparison and visual check therefore both informed candidate rejection.

Modern colour adds two planner profiles. Sunflowers uses the painterly multiscale tangent field with radial petal impasto and softer vase/signature transitions. The Snail and Mondrian use deterministic CIE Lab region segmentation, exact regional mean colours, straight mask-clipped fills and straight contour strokes; neither uses texture noise. Mondrian's elongated dark components use full-length vertical or horizontal strokes rather than dabs.

## Method

- **SSIM:** grayscale, longest side reduced to 384 px.
- **CIE Lab delta E:** CIEDE2000 mean on RGB colours, longest side reduced to 160 px; lower is better.
- **Edge similarity:** overlap of reduced-resolution Sobel magnitude fields; higher is better.
- **Composite:** 55% SSIM + 30% colour similarity + 15% edge similarity, reported on a 0–100 scale. Colour similarity is `clamp(1 - meanΔE/50, 0, 1)`. This is a project comparison index, not an external benchmark.

Scores are rounded only for presentation. The full method and unrounded-input results are stored beside each recipe in `recipes/<id>.score.json`.
