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

/** A spaced, radial-falloff round brush with a small bounded stamp cache. */
export class SoftRoundBrush {
  constructor(ctx, cacheLimit = 160) {
    this.ctx = ctx;
    this.cacheLimit = cacheLimit;
    this.stamps = new Map();
  }

  stamp(size, colour) {
    // Quantisation keeps nearby user brush sizes cache-friendly without changing
    // the stroke path or its visible geometry in any meaningful way.
    const diameter = Math.max(1, Math.round(size * 4) / 4);
    const key = `${diameter}:${colour}`;
    if (this.stamps.has(key)) {
      const cached = this.stamps.get(key);
      this.stamps.delete(key);
      this.stamps.set(key, cached);
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
    stampCtx.globalCompositeOperation = "source-in";
    stampCtx.fillStyle = colour;
    stampCtx.fillRect(0, 0, pixels, pixels);

    this.stamps.set(key, canvas);
    if (this.stamps.size > this.cacheLimit) {
      this.stamps.delete(this.stamps.keys().next().value);
    }
    return canvas;
  }

  paint(stroke) {
    const points = stroke.p || [];
    if (points.length < 2) return;
    const size = Math.max(0.25, Number(stroke.s) || 1);
    const opacity = Math.max(0, Math.min(1, stroke.o === undefined ? 1 : Number(stroke.o)));
    const colour = /^#[0-9a-f]{6}$/i.test(stroke.c) ? stroke.c : "#000000";
    const stamp = this.stamp(size, colour);
    const spacing = Math.max(0.25, size * 0.25);
    const extent = stamp.width;

    const oldAlpha = this.ctx.globalAlpha;
    this.ctx.globalAlpha = opacity;
    let carry = 0;
    let stamped = false;

    const dot = (x, y) => {
      this.ctx.drawImage(stamp, x - extent / 2, y - extent / 2);
      stamped = true;
    };

    dot(points[0], points[1]);
    for (let i = 2; i < points.length; i += 2) {
      const ax = points[i - 2];
      const ay = points[i - 1];
      const bx = points[i];
      const by = points[i + 1];
      const dx = bx - ax;
      const dy = by - ay;
      const length = Math.hypot(dx, dy);
      if (!length) continue;
      let distance = carry === 0 ? spacing : spacing - carry;
      while (distance <= length) {
        const t = distance / length;
        dot(ax + dx * t, ay + dy * t);
        distance += spacing;
      }
      carry = (carry + length) % spacing;
    }
    const lastX = points[points.length - 2];
    const lastY = points[points.length - 1];
    // Include endpoints on short marks and preserve genuinely tiny strokes.
    if (!stamped || Math.hypot(lastX - points[0], lastY - points[1]) < spacing) {
      dot(lastX, lastY);
    } else {
      dot(lastX, lastY);
    }
    this.ctx.globalAlpha = oldAlpha;
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
