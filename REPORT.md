# Painting Cookbook — Score Report

Every score is computed from the stored reference and the PNG emitted by the same `app/brush.js` engine used by the app. Renders contain only canvas-ground plus recipe strokes; no reference pixels are painted.

| Painting | Strokes | SSIM ↑ | Mean CIE ΔE2000 ↓ | Edge similarity ↑ | Composite / 100 ↑ |
|---|---:|---:|---:|---:|---:|
| Mona Lisa | 5,000 | 0.85462 | 1.4395 | 0.76258 | **87.579** |
| Girl with a Pearl Earring | 5,000 | 0.85774 | 1.2760 | 0.79126 | **88.279** |
| The Starry Night | 5,000 | 0.63720 | 3.3062 | 0.68698 | **73.367** |
| The Great Wave off Kanagawa | 5,000 | 0.76292 | 2.4940 | 0.76697 | **81.969** |
| Self-Portrait | 5,000 | 0.64290 | 4.1487 | 0.65555 | **72.704** |
| Lamborghini Countach LP5000 S | 5,000 | 0.66911 | 2.3644 | 0.74728 | **76.592** |
| Audrey Hepburn, Breakfast at Tiffany's | 2,500 | 0.37158 | 3.7158 | 0.36177 | **53.634** |
| Marilyn Monroe | 5,000 | 0.88721 | 1.0718 | 0.80128 | **90.173** |
| The Scream | 5,000 | 0.83248 | 1.9323 | 0.73721 | **85.685** |
| The Blue Marble | 5,000 | 0.67182 | 1.9196 | 0.74967 | **77.043** |
| Sunflowers | 5,000 | 0.78084 | 1.5400 | 0.75553 | **83.355** |
| The Snail | 2,000 | 0.92635 | 1.3608 | 0.80608 | **92.224** |
| Composition with Red, Blue and Yellow | 450 | 0.91877 | 1.4152 | 0.74427 | **90.847** |
| Almond Blossom | 2,800 | 0.68395 | 3.3252 | 0.65722 | **75.481** |
| Woman with a Parasol | 2,400 | 0.68953 | 3.3495 | 0.63320 | **75.413** |
| Wanderer above the Sea of Fog | 2,400 | 0.83050 | 1.7940 | 0.72491 | **85.475** |
| Café Terrace at Night | 2,500 | 0.63650 | 3.9917 | 0.65753 | **72.475** |
| The Fighting Temeraire | 1,800 | 0.86226 | 1.6092 | 0.65686 | **86.312** |
| The Kiss | 2,500 | 0.38610 | 7.0219 | 0.38904 | **52.858** |
| Sunset over a Still Sea | 20 | 0.93770 | 2.0841 | 0.39498 | **86.248** |
| Orange Ball on a Table | 48 | 0.87977 | 2.8026 | 0.34544 | **81.887** |
| Three Hills in Morning Haze | 31 | 0.85205 | 2.7578 | 0.02661 | **75.607** |
| Composition VIII | 450 | 0.36276 | 8.2827 | 0.29935 | **49.472** |
| Impression, Sunrise | 225 | 0.72876 | 3.0616 | 0.32740 | **73.156** |
| Wheatfield with Crows | 450 | 0.39326 | 4.1587 | 0.42271 | **55.475** |
| Nocturne: Blue and Gold – Old Battersea Bridge | 225 | 0.80023 | 1.9213 | 0.50290 | **80.403** |
| Dance | 450 | 0.77239 | 2.9978 | 0.47499 | **77.807** |
| Fine Wind, Clear Morning (Red Fuji) | 450 | 0.50957 | 4.1712 | 0.45193 | **62.302** |
| The Basket of Apples | 900 | 0.65230 | 4.4043 | 0.65089 | **72.997** |
| Sudden Shower over Shin-Ōhashi Bridge | 900 | 0.54070 | 3.0663 | 0.60207 | **66.930** |
| Arrangement in Grey and Black (Whistler's Mother) | 600 | 0.83026 | 1.7868 | 0.62461 | **83.961** |
| American Gothic | 600 | 0.72812 | 3.2207 | 0.62794 | **77.533** |

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
| Mona Lisa | 74.413 | 87.579 | +13.166 |
| Girl with a Pearl Earring | 75.200 | 88.279 | +13.079 |
| The Starry Night | 52.886 | 73.367 | +20.481 |
| The Great Wave off Kanagawa | 62.995 | 81.969 | +18.974 |
| Self-Portrait | 56.791 | 72.704 | +15.913 |

The textured works remain deliberately painterly approximations: their uncorrelated high-frequency canvas texture limits SSIM even when large forms and colours are recognisable. The score comparison and visual check therefore both informed candidate rejection.

Modern colour adds two planner profiles. Sunflowers uses the painterly multiscale tangent field with radial petal impasto and softer vase/signature transitions. The Snail and Mondrian use deterministic CIE Lab region segmentation, exact regional mean colours, straight mask-clipped fills and straight contour strokes; neither uses texture noise. Mondrian's elongated dark components use full-length vertical or horizontal strokes rather than dabs.

## Method

- **SSIM:** grayscale, longest side reduced to 384 px.
- **CIE Lab delta E:** CIEDE2000 mean on RGB colours, longest side reduced to 160 px; lower is better.
- **Edge similarity:** overlap of reduced-resolution Sobel magnitude fields; higher is better.
- **Composite:** 55% SSIM + 30% colour similarity + 15% edge similarity, reported on a 0–100 scale. Colour similarity is `clamp(1 - meanΔE/50, 0, 1)`. This is a project comparison index, not an external benchmark.

Scores are rounded only for presentation. The full method and unrounded-input results are stored beside each recipe in `recipes/<id>.score.json`.
