# Painting Cookbook — Score Report

Every score is computed from the stored reference and the PNG emitted by the same `app/brush.js` engine used by the app. Renders contain only canvas-ground plus recipe strokes; no reference pixels are painted.

| Painting | Strokes | SSIM ↑ | Mean CIE ΔE2000 ↓ | Edge similarity ↑ | Composite / 100 ↑ |
|---|---:|---:|---:|---:|---:|
| Mona Lisa | 5,000 | 0.67728 | 3.2735 | 0.60844 | **74.413** |
| Girl with a Pearl Earring | 5,000 | 0.69257 | 3.0105 | 0.59997 | **75.285** |
| The Starry Night | 5,000 | 0.34555 | 6.1323 | 0.52866 | **53.256** |
| The Great Wave off Kanagawa | 5,000 | 0.51041 | 5.4931 | 0.56423 | **63.240** |
| Self-Portrait | 5,000 | 0.42387 | 6.3552 | 0.50099 | **57.014** |
| Lamborghini Countach LP5000 S | 5,000 | 0.40789 | 6.5291 | 0.54646 | **56.714** |
| Audrey Hepburn, Breakfast at Tiffany's | 2,500 | 0.37158 | 3.7158 | 0.36177 | **53.634** |
| Marilyn Monroe | 5,000 | 0.68283 | 3.0103 | 0.58975 | **74.596** |
| The Scream | 5,000 | 0.59154 | 4.3729 | 0.53287 | **67.904** |
| The Blue Marble | 5,000 | 0.44225 | 4.8302 | 0.53307 | **59.422** |

## Icons — stroke-count selection

Each Icon was planned, rendered and scored independently at all three budgets. The shipped recipe is the smallest measured count within 2.0 composite points of its 5,000-stroke result, with a floor of 1,500 strokes.

| Painting | 1,500 strokes | 2,500 strokes | 5,000 strokes | Shipped | Δ from 5,000 |
|---|---:|---:|---:|---:|---:|
| Lamborghini Countach LP5000 S | 47.695 | 51.445 | 56.714 | **5,000** | +0.000 |
| Audrey Hepburn, Breakfast at Tiffany's | 51.716 | 53.634 | 55.337 | **2,500** | -1.703 |
| Marilyn Monroe | 63.387 | 67.144 | 74.596 | **5,000** | +0.000 |
| The Scream | 51.160 | 60.814 | 67.904 | **5,000** | +0.000 |
| The Blue Marble | 51.616 | 54.951 | 59.422 | **5,000** | +0.000 |

## What changed, and what helped

The deterministic planner progressively unblurs the colour field across four stages, samples positions by colour-change and edge importance, and steers marks with structure-tensor tangents plus painting-specific weak-structure flow. Broad-to-fine multiscale blocking made the largest difference to recognisability; structure-following marks were especially important for Starry Night's currents and Great Wave's nested contours.

After viewing every reference/render pair, a residual-targeted replacement of the final detail stage was tested on all five. It improved Vermeer slightly and was rejected elsewhere. A conservative residual colour-feedback pass then improved four composite scores (all except Mona Lisa) and was retained, mainly through stronger edge agreement. A smaller second feedback pass lowered every composite and was rejected, so iteration stopped and the best five recipes were frozen and rendered again through the shared brush.

| Painting | First verified composite | Final composite | Change |
|---|---:|---:|---:|
| Mona Lisa | 74.413 | 74.413 | +0.000 |
| Girl with a Pearl Earring | 75.200 | 75.285 | +0.085 |
| The Starry Night | 52.886 | 53.256 | +0.370 |
| The Great Wave off Kanagawa | 62.995 | 63.240 | +0.245 |
| Self-Portrait | 56.791 | 57.014 | +0.223 |

The textured works remain deliberately painterly approximations: their uncorrelated high-frequency canvas texture limits SSIM even when large forms and colours are recognisable. The score comparison and visual check therefore both informed candidate rejection.

## Method

- **SSIM:** grayscale, longest side reduced to 384 px.
- **CIE Lab delta E:** CIEDE2000 mean on RGB colours, longest side reduced to 160 px; lower is better.
- **Edge similarity:** overlap of reduced-resolution Sobel magnitude fields; higher is better.
- **Composite:** 55% SSIM + 30% colour similarity + 15% edge similarity, reported on a 0–100 scale. Colour similarity is `clamp(1 - meanΔE/50, 0, 1)`. This is a project comparison index, not an external benchmark.

Scores are rounded only for presentation. The full method and unrounded-input results are stored beside each recipe in `recipes/<id>.score.json`.
