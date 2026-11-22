import { flattenStages, paintStroke, prepareCanvas, renderRecipe } from "./brush.js";

const $ = (id) => document.getElementById(id);
const canvas = $("painting-canvas");
const guide = $("guide-canvas");
const frame = $("canvas-frame");
const ctx = canvas.getContext("2d", { alpha: false });
const guideCtx = guide.getContext("2d");
const descriptions = {
  "mona-lisa": "Veils of earth and gold gather into a famously elusive expression.",
  "girl-with-a-pearl-earring": "A quiet study of darkness, woven colour and one luminous highlight.",
  "starry-night": "The sky is built from moving currents rather than flat blue.",
  "great-wave": "Flat colour becomes motion through nested contours and crisp foam.",
  "van-gogh-self-portrait": "A close, direct likeness assembled from directional colour.",
  "countach": "A wedge drawn in one breath: red planes, black glass and a theatrical rear wing.",
  "marilyn-1953": "Platinum waves frame a face built from soft light and a few decisive accents.",
  "the-scream": "Swirling bands of sky press against the bridge's stark diagonals.",
  "blue-marble": "A luminous disc in pure black, wrapped in white cloud currents.",
  "sunflowers": "A still life built from radiating petals and thick, sunlit colour.",
  "the-snail": "Cut-paper colour turning in on itself, on an orange border.",
  "mondrian-1930": "A measured grid of red, blue, yellow and white held by black bars.",
};
const firstSentence = (text) => (text || "").split(/(?<=[.!?])\s/)[0];

let recipe;
let strokes = [];
let boundaries = [];
let mode = "watch";
let watchCount = 0;
let playing = false;
let animationId = 0;
let paintIndex = 0;
let userStrokes = [];
let drawing = null;
let lessonMode = false;
let autoZoom = true;
let steadyHand = true;
const STEADY = 0.75; // how far a painted point is pulled onto the guide

function boundariesFor(recipeData) {
  let cursor = 0;
  return recipeData.stages.map((stage) => {
    const start = cursor;
    cursor += stage.strokes.length;
    return { start, end: cursor, label: stage.label, tip: stage.tip };
  });
}

function stageIndexAt(count) {
  const index = boundaries.findIndex((stage) => count >= stage.start && count < stage.end);
  return index < 0 ? boundaries.length - 1 : index;
}

const counterText = (count) => `${count.toLocaleString()} / ${strokes.length.toLocaleString()}`;

function updateWatchUI() {
  const total = strokes.length;
  const stageIndex = watchCount === 0 ? -1 : stageIndexAt(watchCount - 1);
  $("stroke-counter").textContent = counterText(watchCount);
  $("scrubber").value = watchCount;
  $("stage-name").textContent = watchCount === 0 ? "Blank canvas" : watchCount === total ? "Finished" : boundaries[stageIndex]?.label || "";
  $("play-button").textContent = playing ? "❚❚ Pause" : watchCount === total ? "▶ Replay" : "▶ Play";
  [...$("stage-buttons").children].forEach((button, index) => button.classList.toggle("active", index === stageIndex));
  $("canvas-status").textContent = "";
}

function pauseReplay() {
  playing = false;
  if (animationId) cancelAnimationFrame(animationId);
  animationId = 0;
  if (mode === "watch") updateWatchUI();
}

function clearStudy() {
  prepareCanvas(ctx, recipe);
  guideCtx.clearRect(0, 0, guide.width, guide.height);
}

function setWatchCount(count) {
  pauseReplay();
  const target = Math.max(0, Math.min(strokes.length, Math.round(count)));
  if (target === 0 || target < watchCount) {
    // Going back: repaint from the start.
    clearStudy();
    renderRecipe(ctx, recipe, 0, target);
  } else {
    // Going forward: only paint the strokes in between.
    renderRecipe(ctx, recipe, watchCount, target);
  }
  watchCount = target;
  updateWatchUI();
}

// Coalesce slider input to at most one repaint per frame.
let pendingScrub = null;
function scrubTo(value) {
  const first = pendingScrub === null;
  pendingScrub = value;
  if (first) requestAnimationFrame(() => {
    const target = pendingScrub;
    pendingScrub = null;
    setWatchCount(target);
  });
}

function playReplay() {
  if (playing) return pauseReplay();
  if (watchCount >= strokes.length) setWatchCount(0);
  playing = true;
  let last = performance.now();
  let fraction = 0;
  const tick = (now) => {
    if (!playing || mode !== "watch") return;
    const elapsed = Math.min(0.12, (now - last) / 1000);
    last = now;
    fraction += elapsed * Number($("speed").value);
    const amount = Math.min(Math.floor(fraction), strokes.length - watchCount);
    if (amount > 0) {
      fraction -= amount;
      const stop = watchCount + amount;
      renderRecipe(ctx, recipe, watchCount, stop);
      watchCount = stop;
      updateWatchUI();
    }
    if (watchCount >= strokes.length) return pauseReplay();
    animationId = requestAnimationFrame(tick);
  };
  updateWatchUI();
  animationId = requestAnimationFrame(tick);
}

function clearGuide() {
  guideCtx.clearRect(0, 0, guide.width, guide.height);
}

function showGhost() {
  clearGuide();
  if (mode !== "paint" || paintIndex >= strokes.length) return;
  // The guide is one continuous shape: a soft band at the real brush width,
  // a thin solid centre line, and a dot where the stroke starts.
  const drawGhost = (stroke, next = false) => {
    const points = stroke.p;
    const path = () => {
      guideCtx.beginPath();
      guideCtx.moveTo(points[0], points[1]);
      for (let i = 2; i < points.length; i += 2) guideCtx.lineTo(points[i], points[i + 1]);
    };
    guideCtx.save();
    guideCtx.lineCap = "round";
    guideCtx.lineJoin = "round";
    guideCtx.strokeStyle = stroke.c;
    if (!next) {
      // A thin dark rim keeps the band visible even when its colour matches the canvas.
      path();
      guideCtx.globalAlpha = 0.35;
      guideCtx.strokeStyle = "#252720";
      guideCtx.lineWidth = Math.max(2, stroke.s * 0.9) + 3;
      guideCtx.stroke();
      guideCtx.strokeStyle = stroke.c;
    }
    path();
    guideCtx.globalAlpha = next ? 0.12 : 0.55;
    guideCtx.lineWidth = Math.max(2, stroke.s * 0.9);
    guideCtx.stroke();
    if (!next) {
      path();
      guideCtx.globalAlpha = 0.95;
      guideCtx.strokeStyle = "#ffffff";
      guideCtx.lineWidth = Math.max(1.5, Math.min(4, stroke.s * 0.08)) + 2;
      guideCtx.stroke();
      path();
      guideCtx.strokeStyle = stroke.c;
      guideCtx.lineWidth = Math.max(1.5, Math.min(4, stroke.s * 0.08));
      guideCtx.stroke();
      guideCtx.beginPath();
      const r = Math.max(4, Math.min(10, stroke.s * 0.25));
      guideCtx.arc(Math.min(Math.max(points[0], r + 2), guide.width - r - 2), Math.min(Math.max(points[1], r + 2), guide.height - r - 2), r, 0, Math.PI * 2);
      guideCtx.fillStyle = stroke.c;
      guideCtx.fill();
      guideCtx.lineWidth = 2;
      guideCtx.strokeStyle = "#ffffff";
      guideCtx.stroke();
    }
    guideCtx.restore();
  };
  if (lessonMode && strokes[paintIndex + 1]) drawGhost(strokes[paintIndex + 1], true);
  drawGhost(strokes[paintIndex]);
}

function updatePaintUI() {
  const stroke = strokes[paintIndex];
  $("stroke-counter").textContent = counterText(paintIndex);
  $("undo-button").disabled = paintIndex === 0;
  $("skip-button").disabled = !stroke;
  if (!stroke) {
    $("stage-name").textContent = "Finished — well done";
    $("stage-tip").hidden = true;
    $("next-swatch").style.background = "var(--sage)";
    $("brush-size").textContent = "";
    $("canvas-status").textContent = "";
    clearGuide();
    applyZoom();
    return;
  }
  const stage = boundaries[stageIndexAt(paintIndex)];
  $("stage-name").textContent = stage?.label || "";
  $("stage-tip").textContent = stage?.tip || "";
  $("stage-tip").hidden = !(lessonMode && stage?.tip);
  $("next-swatch").style.background = stroke.c;
  $("brush-size").textContent = `${stroke.s} px`;
  $("canvas-status").textContent = paintIndex === 0 ? "Start at the dot and paint over the shaded stroke in one go" : "";
  showGhost();
  applyZoom();
}

// Zoom the view so small strokes are at least ~16 px wide on screen.
function applyZoom() {
  const stroke = mode === "paint" ? strokes[paintIndex] : null;
  let transform = "";
  if (autoZoom && stroke) {
    const scale = frame.clientWidth / recipe.width; // screen px per painting px
    const onScreen = stroke.s * scale;
    const zoom = Math.min(4, Math.max(1, 16 / onScreen));
    if (zoom > 1.15) {
      const xs = stroke.p.filter((_, i) => i % 2 === 0), ys = stroke.p.filter((_, i) => i % 2 === 1);
      const cx = (Math.min(...xs) + Math.max(...xs)) / 2 * scale;
      const cy = (Math.min(...ys) + Math.max(...ys)) / 2 * scale;
      const fw = frame.clientWidth, fh = frame.clientHeight;
      const tx = Math.min(0, Math.max(fw - fw * zoom, fw / 2 - cx * zoom));
      const ty = Math.min(0, Math.max(fh - fh * zoom, fh / 2 - cy * zoom));
      transform = `translate(${tx}px, ${ty}px) scale(${zoom})`;
    }
  }
  canvas.style.transform = guide.style.transform = transform;
}

// Pull a point most of the way onto the nearest point of the guide stroke.
function steady(x, y) {
  if (!steadyHand) return [x, y];
  const p = strokes[paintIndex].p;
  let best = [p[0], p[1]], bestD = Infinity;
  for (let i = 0; i + 3 < p.length || i === 0; i += 2) {
    const ax = p[i], ay = p[i + 1], bx = p[i + 2] ?? ax, by = p[i + 3] ?? ay;
    const dx = bx - ax, dy = by - ay, len = dx * dx + dy * dy;
    const t = len ? Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / len)) : 0;
    const qx = ax + dx * t, qy = ay + dy * t, d = (qx - x) ** 2 + (qy - y) ** 2;
    if (d < bestD) { bestD = d; best = [qx, qy]; }
    if (p.length < 4) break;
  }
  return [x + (best[0] - x) * STEADY, y + (best[1] - y) * STEADY];
}

// Paint progress is saved in this browser per painting, so you can continue later.
const progressKey = () => `paintcrastinator:${recipe.id}`;
function saveProgress() {
  try {
    if (!userStrokes.length) { localStorage.removeItem(progressKey()); return; }
    localStorage.setItem(progressKey(), JSON.stringify({ i: paintIndex, p: userStrokes.map((s) => s.p.map((v) => Math.round(v * 10) / 10)) }));
  } catch { /* storage full or blocked: painting still works, it just is not saved */ }
}
function restoreProgress() {
  paintIndex = 0;
  userStrokes = [];
  try {
    const saved = JSON.parse(localStorage.getItem(progressKey()) || "null");
    if (saved && Array.isArray(saved.p) && saved.p.length === saved.i && saved.i <= strokes.length) {
      userStrokes = saved.p.map((p, k) => ({ p, c: strokes[k].c, s: strokes[k].s, o: strokes[k].o }));
      paintIndex = saved.i;
    }
  } catch { /* ignore bad or blocked storage */ }
  userStrokes.forEach((stroke) => paintStroke(ctx, stroke));
  return paintIndex;
}

function setMode(nextMode) {
  pauseReplay();
  mode = nextMode;
  const isPaint = mode === "paint";
  $("watch-mode").classList.toggle("active", !isPaint);
  $("paint-mode").classList.toggle("active", isPaint);
  $("watch-mode").setAttribute("aria-pressed", String(!isPaint));
  $("paint-mode").setAttribute("aria-pressed", String(isPaint));
  $("watch-controls").hidden = isPaint;
  $("paint-controls").hidden = !isPaint;
  $("stage-tip").hidden = true;
  frame.classList.toggle("painting", isPaint);
  clearStudy();
  if (isPaint) {
    const resumed = restoreProgress();
    updatePaintUI();
    if (resumed > 0) $("canvas-status").textContent = `Welcome back — continuing from stroke ${resumed.toLocaleString()}`;
  } else {
    watchCount = 0;
    updateWatchUI();
    applyZoom();
  }
}

function eventPoint(event) {
  const rect = canvas.getBoundingClientRect();
  return [
    Math.max(0, Math.min(recipe.width, (event.clientX - rect.left) * recipe.width / rect.width)),
    Math.max(0, Math.min(recipe.height, (event.clientY - rect.top) * recipe.height / rect.height)),
  ];
}

function beginPaint(event) {
  if (mode !== "paint" || paintIndex >= strokes.length || drawing) return;
  event.preventDefault();
  canvas.setPointerCapture(event.pointerId);
  const [x, y] = steady(...eventPoint(event));
  const guideStroke = strokes[paintIndex];
  drawing = { pointerId: event.pointerId, points: [x, y] };
  paintStroke(ctx, { p: [x, y, x + 0.01, y], c: guideStroke.c, s: guideStroke.s, o: guideStroke.o });
  $("canvas-status").textContent = "";
}

function movePaint(event) {
  if (!drawing || event.pointerId !== drawing.pointerId) return;
  event.preventDefault();
  const [x, y] = steady(...eventPoint(event));
  const points = drawing.points;
  const ax = points[points.length - 2];
  const ay = points[points.length - 1];
  const guideStroke = strokes[paintIndex];
  if (Math.hypot(x - ax, y - ay) < Math.max(0.75, guideStroke.s * 0.16)) return;
  points.push(x, y);
  paintStroke(ctx, { p: [ax, ay, x, y], c: guideStroke.c, s: guideStroke.s, o: guideStroke.o });
}

function finishPaint(event) {
  if (!drawing || event.pointerId !== drawing.pointerId) return;
  event.preventDefault();
  const guideStroke = strokes[paintIndex];
  userStrokes.push({ p: drawing.points, c: guideStroke.c, s: guideStroke.s, o: guideStroke.o });
  drawing = null;
  if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
  paintIndex += 1;
  updatePaintUI();
  saveProgress();
}

function repaintUserStrokes() {
  clearStudy();
  userStrokes.forEach((stroke) => paintStroke(ctx, stroke));
  updatePaintUI();
}

function buildStageButtons() {
  $("stage-buttons").replaceChildren(...boundaries.map((stage, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "stage-button";
    button.innerHTML = `<span>${index + 1}</span>${stage.label}`;
    button.setAttribute("aria-label", `Show the painting up to ${stage.label}`);
    button.addEventListener("click", () => setWatchCount(stage.end));
    return button;
  }));
}

// One short credit line: "[Photo: name, ]licence · source".
function showReferenceCredit(credit) {
  const element = $("reference-credit");
  element.replaceChildren();
  element.hidden = !credit;
  if (!credit) return;
  if (credit.licence === "CC BY-SA 4.0") {
    const licence = document.createElement("a");
    licence.href = "https://creativecommons.org/licenses/by-sa/4.0/";
    licence.textContent = credit.licence;
    element.append(document.createTextNode(`Photo: ${credit.author}, `), licence);
  } else {
    element.append(document.createTextNode(credit.licence));
  }
  const source = document.createElement("a");
  source.href = credit.url;
  source.textContent = credit.source || "Wikimedia Commons";
  element.append(document.createTextNode(" · "), source);
}

async function load() {
  const id = new URLSearchParams(location.search).get("id");
  if (!id || !/^[a-z0-9-]+$/.test(id)) throw new Error("No painting was chosen.");
  const [recipeResponse, manifestResponse] = await Promise.all([fetch(`../recipes/${id}.json`), fetch("../recipes/manifest.json")]);
  if (!recipeResponse.ok) throw new Error(`Recipe returned ${recipeResponse.status}`);
  recipe = await recipeResponse.json();
  if (manifestResponse.ok) {
    const entry = (await manifestResponse.json()).find((item) => item.id === id);
    recipe.credit = entry?.credit || recipe.credit;
    recipe.reference = recipe.reference || entry?.reference;
  }
  strokes = flattenStages(recipe);
  boundaries = boundariesFor(recipe);
  if (!strokes.length) throw new Error("This recipe has no strokes.");
  lessonMode = strokes.length < 1000;
  document.title = `${recipe.title} — Paintcrastinator`;
  $("painting-title").textContent = recipe.title;
  const lesson = id.startsWith("lesson-");
  $("artist-line").textContent = lesson ? "Lesson" : `${recipe.artist} · ${recipe.year}`;
  $("reference-image").src = `../${(recipe.reference || `references/${id}.jpg`).replace(/^(\.\.\/)+/, "")}`;
  $("reference-image").alt = `Original: ${recipe.title}`;
  showReferenceCredit(lesson ? null : recipe.credit);
  $("study-description").textContent = recipe.lessonTip || firstSentence(descriptions[id] || recipe.description);
  $("scrubber").max = strokes.length;
  const defaultSpeed = Math.max(10, Math.min(500, Math.round(strokes.length / 20 / 10) * 10));
  $("speed").value = defaultSpeed;
  $("speed-output").textContent = `${defaultSpeed}/s`;
  canvas.width = guide.width = recipe.width;
  canvas.height = guide.height = recipe.height;
  frame.style.aspectRatio = `${recipe.width} / ${recipe.height}`;
  // Fit the whole canvas in the window: limit its width by the available height.
  frame.style.maxWidth = `calc((100vh - 330px) * ${(recipe.width / recipe.height).toFixed(4)})`;
  buildStageButtons();
  setWatchCount(0);
  $("study").hidden = false;
}

$("watch-mode").addEventListener("click", () => setMode("watch"));
$("zoom-toggle").addEventListener("click", () => {
  autoZoom = !autoZoom;
  $("zoom-toggle").setAttribute("aria-pressed", String(autoZoom));
  applyZoom();
});
$("steady-toggle").addEventListener("click", () => {
  steadyHand = !steadyHand;
  $("steady-toggle").setAttribute("aria-pressed", String(steadyHand));
});
addEventListener("resize", () => applyZoom());
$("paint-mode").addEventListener("click", () => setMode("paint"));
$("play-button").addEventListener("click", playReplay);
$("speed").addEventListener("input", () => { $("speed-output").textContent = `${$("speed").value}/s`; });
$("scrubber").addEventListener("input", () => scrubTo(Number($("scrubber").value)));
$("undo-button").addEventListener("click", () => {
  if (paintIndex > 0) {
    paintIndex -= 1;
    userStrokes.pop();
    repaintUserStrokes();
    saveProgress();
  }
});
$("skip-button").addEventListener("click", () => {
  if (mode !== "paint" || paintIndex >= strokes.length) return;
  const stage = boundaries[stageIndexAt(paintIndex)];
  while (paintIndex < stage.end) {
    const stroke = strokes[paintIndex];
    paintStroke(ctx, stroke);
    userStrokes.push(stroke);
    paintIndex += 1;
  }
  updatePaintUI();
  saveProgress();
});
$("restart-button").addEventListener("click", () => {
  paintIndex = 0;
  userStrokes = [];
  drawing = null;
  repaintUserStrokes();
  saveProgress();
});
canvas.addEventListener("pointerdown", beginPaint);
canvas.addEventListener("pointermove", movePaint);
canvas.addEventListener("pointerup", finishPaint);
canvas.addEventListener("pointercancel", finishPaint);

load().catch((error) => {
  $("load-error").hidden = false;
  $("error-message").textContent = error.message;
});
