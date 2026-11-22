/*
 * Painting Cookbook's only raster brush.
 * Used by the offline renderer, watch replay, and paint-along canvas.
 */

const engines = new WeakMap();

function makeCanvas(width, height, host) {
  const doc = host?.ownerDocument || globalThis.document;
  if (doc) {
    const canvas = doc.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    return canvas;
  }
  if (globalThis.OffscreenCanvas) return new OffscreenCanvas(width, height);
  throw new Error("A canvas implementation is required");
}

/**
 * A spaced, radial-falloff round brush.
 *
 * Memory-safe version: one white alpha stamp per brush size (a small bounded cache),
 * and one reusable scratch canvas per brush. Each stroke's stamps are accumulated on
 * the scratch canvas with the stroke's opacity, the scratch is tinted with the stroke
 * colour, and the result is drawn once. For a single colour this gives exactly the
 * same pixels as stamping the colour directly onto the painting
 * (c + (C - c) * prod(1 - o * a_i)), without creating a canvas per colour.
 */
export class SoftRoundBrush {
  constructor(ctx, cacheLimit = 96) {
    this.ctx = ctx;
    this.cacheLimit = cacheLimit;
    this.stamps = new Map();
    this.scratch = null;
    this.scratchCtx = null;
  }

  stamp(size) {
    const diameter = Math.max(1, Math.round(size * 4) / 4);
    if (this.stamps.has(diameter)) {
      const cached = this.stamps.get(diameter);
      this.stamps.delete(diameter);
      this.stamps.set(diameter, cached);
      return cached;
    }
    const radius = diameter / 2;
    const pixels = Math.max(2, Math.ceil(diameter) + 2);
    const canvas = makeCanvas(pixels, pixels, this.ctx.canvas);
    const stampCtx = canvas.getContext("2d");
    const centre = pixels / 2;
    const gradient = stampCtx.createRadialGradient(centre, centre, 0, centre, centre, radius);
    gradient.addColorStop(0, "rgba(255,255,255,1)");
    gradient.addColorStop(0.28, "rgba(255,255,255,0.98)");
    gradient.addColorStop(0.62, "rgba(255,255,255,0.82)");
    gradient.addColorStop(0.84, "rgba(255,255,255,0.43)");
    gradient.addColorStop(1, "rgba(255,255,255,0)");
    stampCtx.fillStyle = gradient;
    stampCtx.fillRect(0, 0, pixels, pixels);
    this.stamps.set(diameter, canvas);
    if (this.stamps.size > this.cacheLimit) {
      const oldest = this.stamps.keys().next().value;
      const dropped = this.stamps.get(oldest);
      dropped.width = dropped.height = 0; // release the bitmap now (helps mobile Safari)
      this.stamps.delete(oldest);
    }
    return canvas;
  }

  scratchFor(width, height) {
    if (!this.scratch || this.scratch.width < width || this.scratch.height < height) {
      const w = Math.max(width, this.scratch?.width || 0, 64);
      const h = Math.max(height, this.scratch?.height || 0, 64);
      if (this.scratch) this.scratch.width = this.scratch.height = 0;
      this.scratch = makeCanvas(w, h, this.ctx.canvas);
      this.scratchCtx = this.scratch.getContext("2d");
    }
    return this.scratchCtx;
  }

  paint(stroke) {
    const points = stroke.p || [];
    if (points.length < 2) return;
    const size = Math.max(0.25, Number(stroke.s) || 1);
    const opacity = Math.max(0, Math.min(1, stroke.o === undefined ? 1 : Number(stroke.o)));
    const colour = /^#[0-9a-f]{6}$/i.test(stroke.c) ? stroke.c : "#000000";
    const stamp = this.stamp(size);
    const spacing = Math.max(0.25, size * 0.25);
    const extent = stamp.width;

    // Stamp centres, exactly as before.
    const centres = [points[0], points[1]];
    let carry = 0;
    for (let i = 2; i < points.length; i += 2) {
      const ax = points[i - 2];
      const ay = points[i - 1];
      const dx = points[i] - ax;
      const dy = points[i + 1] - ay;
      const length = Math.hypot(dx, dy);
      if (!length) continue;
      let distance = carry === 0 ? spacing : spacing - carry;
      while (distance <= length) {
        const t = distance / length;
        centres.push(ax + dx * t, ay + dy * t);
        distance += spacing;
      }
      carry = (carry + length) % spacing;
    }
    centres.push(points[points.length - 2], points[points.length - 1]);

    // Integer bounding box, so every stamp keeps its sub-pixel offset.
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (let i = 0; i < centres.length; i += 2) {
      minX = Math.min(minX, centres[i]); maxX = Math.max(maxX, centres[i]);
      minY = Math.min(minY, centres[i + 1]); maxY = Math.max(maxY, centres[i + 1]);
    }
    const x0 = Math.floor(minX - extent / 2) - 1;
    const y0 = Math.floor(minY - extent / 2) - 1;
    const w = Math.ceil(maxX + extent / 2) + 2 - x0;
    const h = Math.ceil(maxY + extent / 2) + 2 - y0;
    const sc = this.scratchFor(w, h);
    sc.save();
    sc.globalCompositeOperation = "source-over";
    sc.globalAlpha = 1;
    sc.clearRect(0, 0, w, h);
    sc.globalAlpha = opacity;
    for (let i = 0; i < centres.length; i += 2) sc.drawImage(stamp, centres[i] - extent / 2 - x0, centres[i + 1] - extent / 2 - y0);
    sc.globalAlpha = 1;
    sc.globalCompositeOperation = "source-in";
    sc.fillStyle = colour;
    sc.fillRect(0, 0, w, h);
    sc.restore();
    this.ctx.drawImage(this.scratch, 0, 0, w, h, x0, y0, w, h);
  }
}

export function brushFor(ctx) {
  let brush = engines.get(ctx);
  if (!brush) {
    brush = new SoftRoundBrush(ctx);
    engines.set(ctx, brush);
  }
  return brush;
}

export function paintStroke(ctx, stroke) {
  brushFor(ctx).paint(stroke);
}

export function flattenStages(recipe) {
  if (Array.isArray(recipe.strokes)) return recipe.strokes;
  return (recipe.stages || []).flatMap((stage) => stage.strokes || []);
}

export function prepareCanvas(ctx, recipe) {
  ctx.save();
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = "source-over";
  ctx.fillStyle = recipe.ground || "#ffffff";
  ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
  ctx.restore();
}

export function renderRecipe(ctx, recipe, start = 0, end = Infinity) {
  const strokes = flattenStages(recipe);
  const stop = Math.min(strokes.length, end);
  for (let i = Math.max(0, start); i < stop; i += 1) paintStroke(ctx, strokes[i]);
  return stop;
}
