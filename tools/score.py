#!/usr/bin/env python3
"""Deterministic, reduced-resolution perceptual scoring for rendered recipes."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.color import deltaE_ciede2000, rgb2lab
from skimage.filters import sobel
from skimage.metrics import structural_similarity
from skimage.transform import resize


def rgb_array(path):
    image = Image.open(path)
    if image.mode == "RGBA":
        base = Image.new("RGBA", image.size, "white")
        image = Image.alpha_composite(base, image)
    return np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0


def reduce(image, longest):
    scale = min(1.0, longest / max(image.shape[:2]))
    shape = (max(1, round(image.shape[0] * scale)), max(1, round(image.shape[1] * scale)))
    return resize(image, shape, order=1, anti_aliasing=True, preserve_range=True)


def score(reference_path, render_path):
    reference = rgb_array(reference_path)
    render = rgb_array(render_path)
    if reference.shape != render.shape:
        raise ValueError(f"Size mismatch: reference {reference.shape}, render {render.shape}")

    a = reduce(reference, 384)
    b = reduce(render, 384)
    gray_a = np.dot(a[..., :3], [0.2126, 0.7152, 0.0722])
    gray_b = np.dot(b[..., :3], [0.2126, 0.7152, 0.0722])
    ssim = float(structural_similarity(gray_a, gray_b, data_range=1.0))

    # A modest fixed grid prevents this metric from rewarding tiny noise.
    grid_a = reduce(reference, 160)
    grid_b = reduce(render, 160)
    delta_grid = deltaE_ciede2000(rgb2lab(grid_a), rgb2lab(grid_b))
    delta_e = float(np.mean(delta_grid))
    colour_similarity = float(np.clip(1.0 - delta_e / 50.0, 0.0, 1.0))

    edge_a = sobel(gray_a)
    edge_b = sobel(gray_b)
    denominator = float(np.sum(edge_a) + np.sum(edge_b))
    edge_similarity = float(2.0 * np.minimum(edge_a, edge_b).sum() / denominator) if denominator else 1.0
    similarity = float(100.0 * (0.55 * ssim + 0.30 * colour_similarity + 0.15 * edge_similarity))
    return {
        "reference": str(reference_path),
        "render": str(render_path),
        "ssim": round(ssim, 5),
        "mean_delta_e": round(delta_e, 4),
        "edge_similarity": round(edge_similarity, 5),
        "colour_similarity": round(colour_similarity, 5),
        "similarity": round(similarity, 3),
        "method": "SSIM: grayscale, 384px longest side; deltaE2000: RGB Lab, 160px longest side; edges: reduced Sobel overlap; overall: 55% SSIM + 30% colour + 15% edges",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("render", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = score(args.reference, args.render)
    text = json.dumps(result, indent=2)
    print(text)
    if args.output:
        args.output.write_text(text + "\n")


if __name__ == "__main__":
    main()
