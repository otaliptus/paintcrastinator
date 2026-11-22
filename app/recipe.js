import { flattenStages, paintStroke, prepareCanvas, renderRecipe } from "./brush.js";

const $ = (id) => document.getElementById(id);
const canvas = $("painting-canvas");
const guide = $("guide-canvas");
const frame = $("canvas-frame");
const ctx = canvas.getContext("2d", { alpha: false });
const guideCtx = guide.getContext("2d");
const descriptions = {
  "mona-lisa": "Veils of earth and gold gather into a famously elusive expression. Broad masses give way to small, contour-following touches.",
  "girl-with-a-pearl-earring": "A quiet study of darkness, woven colour and one luminous highlight. Follow the headcloth before resolving the face and pearl.",
  "starry-night": "The sky is built from moving currents rather than flat blue. Curved marks gather into eddies, stars and the dark vertical accent below.",
  "great-wave": "Flat colour becomes motion through nested contours and crisp foam marks. Small late strokes carry the rhythm of the woodblock printed lines.",
  "van-gogh-self-portrait": "A close, direct likeness assembled from directional colour. Background strokes and facial marks retain the energy of the painted surface.",
  "countach": "A wedge drawn in one breath: red planes, black glass and a theatrical rear wing. Chrome-bright wheels and a taut silhouette carry the final marks.",
  "breakfast-at-tiffanys": "A near-black silhouette against a screen of soft pale blocks. Face, hair bun, long gloves and the slender cigarette holder receive the decisive marks.",
  "marilyn-1953": "Platinum waves frame a face built from soft light and a few decisive accents. Eyes, lips and the hairline receive the smallest, sharpest strokes.",
  "the-scream": "Swirling bands of sky press against the bridge's stark diagonals. A lone figure gathers from pulsing colour and a few dark, insistent contours.",
  "blue-marble": "A luminous disc suspended in pure black. White cloud currents and ochre lands follow the turning surface of the Earth.",
  "sunflowers": "A still life built from radiating petals and thick, sunlit colour. Follow the flower heads before the vase's soft blue line and signature.",
  "the-snail": "Cut-paper colour turns in on itself. Flat, exact colour shapes settle onto an orange border, followed by straight strokes along their crisp edges.",
  "mondrian-1930": "A measured grid of red, blue, yellow and white. Long black bars hold the structure while flat colour and straight edge marks bring each plane into focus.",
};

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
let referenceReady = false;
let lessonMode = false;
const referenceScoreCanvas = document.createElement("canvas");
const paintingScoreCanvas = document.createElement("canvas");

function boundariesFor(recipeData) {
  let cursor = 0;
  return recipeData.stages.map((stage) => {
    const start = cursor;
    cursor += stage.strokes.length;
    return { start, end: cursor, id: stage.id, label: stage.label, tip: stage.tip };
  });
}

function stageAt(count) {
  if (count === 0) return -1;
  const index = boundaries.findIndex((stage) => count <= stage.end && count > stage.start);
  return index < 0 ? boundaries.length - 1 : index;
}

function updateWatchUI() {
  const total = strokes.length;
  const stageIndex = stageAt(watchCount);
  $("stroke-counter").textContent = `${watchCount.toLocaleString()} / ${total.toLocaleString()} strokes`;
  $("top-stroke-counter").textContent = `${watchCount.toLocaleString()} / ${total.toLocaleString()} strokes`;
  $("reference-progress").value = watchCount;
  $("reference-percent").textContent = `${Math.round(watchCount / total * 100)}%`;
  $("reference-stage").textContent = watchCount === 0 ? "Blank canvas" : watchCount === total ? "Finished study" : boundaries[stageIndex]?.label;
  $("scrubber").value = watchCount;
  $("stage-name").textContent = watchCount === 0 ? "Blank canvas" : boundaries[stageIndex]?.label || "Fine details";
  $("stage-kicker").textContent = watchCount === total ? "FINISHED STUDY" : watchCount === 0 ? "READY TO REPLAY" : `REPLAY · STAGE ${stageIndex + 1}`;
  $("play-button").innerHTML = playing ? "❚❚ <span>Pause</span>" : watchCount === total ? "▶ <span>Replay</span>" : "▶ <span>Play</span>";
  $("play-button").setAttribute("aria-label", playing ? "Pause painting replay" : "Play painting replay");
  [...$("stage-buttons").children].forEach((button, index) => button.classList.toggle("active", index === stageIndex));
  $("canvas-status").textContent = mode === "watch" && watchCount === 0 ? "Press play, or choose a stage" : "";
}

function pauseReplay() {
  playing = false;
  if (animationId) cancelAnimationFrame(animationId);
  animationId = 0;
  updateWatchUI();
}

function clearStudy() {
  prepareCanvas(ctx, recipe);
  guideCtx.clearRect(0, 0, guide.width, guide.height);
}

function setWatchCount(count) {
  pauseReplay();
  clearStudy();
  watchCount = Math.max(0, Math.min(strokes.length, Math.round(count)));
  renderRecipe(ctx, recipe, 0, watchCount);
  updateWatchUI();
}

function playReplay() {
  if (playing) {
    pauseReplay();
    return;
  }
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
    if (watchCount >= strokes.length) {
      pauseReplay();
      return;
    }
    animationId = requestAnimationFrame(tick);
  };
  updateWatchUI();
  animationId = requestAnimationFrame(tick);
}

function clearGuide() {
  guideCtx.clearRect(0, 0, guide.width, guide.height);
  guide.dataset.ghostStrokes = "0";
}

function showGhost() {
  clearGuide();
  if (mode !== "paint" || paintIndex >= strokes.length) return;
  const drawGhost = (stroke, next = false) => {
    const points = stroke.p;
    guideCtx.save();
    guideCtx.beginPath();
    guideCtx.moveTo(points[0], points[1]);
    for (let i = 2; i < points.length; i += 2) guideCtx.lineTo(points[i], points[i + 1]);
    guideCtx.strokeStyle = stroke.c;
    guideCtx.globalAlpha = next ? 0.16 : lessonMode ? 0.90 : 0.48;
    guideCtx.lineWidth = next ? Math.max(1, stroke.s * 0.08) : lessonMode ? Math.max(2.4, stroke.s * 0.22) : Math.max(1.2, stroke.s * 0.12);
    guideCtx.lineCap = "round";
    guideCtx.lineJoin = "round";
    guideCtx.setLineDash([Math.max(2, stroke.s * (next ? 0.18 : 0.28)), Math.max(3, stroke.s * 0.32)]);
    guideCtx.stroke();
    guideCtx.setLineDash([]);
    if (!next) {
      guideCtx.globalAlpha = lessonMode ? 1 : 0.75;
      guideCtx.beginPath();
      guideCtx.arc(points[0], points[1], Math.max(2, stroke.s * (lessonMode ? 0.22 : 0.16)), 0, Math.PI * 2);
      guideCtx.fillStyle = stroke.c;
      guideCtx.fill();
    }
    guideCtx.restore();
  };
  if (lessonMode && strokes[paintIndex + 1]) drawGhost(strokes[paintIndex + 1], true);
  drawGhost(strokes[paintIndex]);
  guide.dataset.ghostStrokes = lessonMode && strokes[paintIndex + 1] ? "2" : "1";
  guide.dataset.lessonGhost = String(lessonMode);
  $("canvas-status").textContent = "Drag along the dashed guide";
}

function updateGuideUI() {
  const stroke = strokes[paintIndex];
  $("stroke-counter").textContent = `${paintIndex.toLocaleString()} / ${strokes.length.toLocaleString()} strokes`;
  $("top-stroke-counter").textContent = `${paintIndex.toLocaleString()} / ${strokes.length.toLocaleString()} strokes`;
  $("reference-progress").value = paintIndex;
  $("reference-percent").textContent = `${Math.round(paintIndex / strokes.length * 100)}%`;
  const activeStageIndex = paintIndex >= strokes.length ? boundaries.length - 1 : boundaries.findIndex((boundary) => paintIndex >= boundary.start && paintIndex < boundary.end);
  $("reference-stage").textContent = paintIndex >= strokes.length ? "Your painted version" : boundaries[activeStageIndex]?.label;
  $("skip-button").disabled = paintIndex >= strokes.length;
  if (!stroke) {
    $("stage-kicker").textContent = "STUDY COMPLETE";
    $("stage-name").textContent = "Your painted version";
    $("guide-number").textContent = "complete";
    $("guide-instruction").textContent = "Every guided mark is painted";
    $("brush-size").textContent = "✓";
    $("next-swatch").style.background = "var(--sage)";
    $("canvas-status").textContent = "Study complete — beautiful work";
    $("undo-button").disabled = paintIndex === 0;
    clearGuide();
    return;
  }
  const stageIndex = boundaries.findIndex((boundary) => paintIndex >= boundary.start && paintIndex < boundary.end);
  $("stage-kicker").textContent = `PAINT ALONG · STAGE ${stageIndex + 1}`;
  $("stage-name").textContent = boundaries[stageIndex]?.label || "Guided study";
  $("guide-number").textContent = `${paintIndex + 1} of ${strokes.length}`;
  $("guide-instruction").textContent = "Colour and size are supplied";
  $("stage-tip").textContent = boundaries[stageIndex]?.tip || "Follow the current stroke; the faint mark shows what comes next.";
  $("brush-size").textContent = `${stroke.s} px brush`;
  $("next-swatch").style.background = stroke.c;
  $("undo-button").disabled = paintIndex === 0;
  showGhost();
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
  frame.classList.toggle("painting", isPaint);
  frame.classList.toggle("lesson-mode", isPaint && lessonMode);
  $("stage-tip").hidden = !(isPaint && lessonMode);
  $("mode-hint").textContent = isPaint ? "Your gesture. The recipe's colour and brush." : "From the first broad mark to the final detail.";
  clearStudy();
  if (isPaint) {
    paintIndex = 0;
    userStrokes = [];
    $("live-score").textContent = "—";
    updateGuideUI();
    updateLiveScore();
  } else {
    watchCount = 0;
    updateWatchUI();
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
  const [x, y] = eventPoint(event);
  const guideStroke = strokes[paintIndex];
  drawing = { pointerId: event.pointerId, points: [x, y] };
  paintStroke(ctx, { p: [x, y, x + 0.01, y], c: guideStroke.c, s: guideStroke.s, o: guideStroke.o });
  $("canvas-status").textContent = "Painting…";
}

function movePaint(event) {
  if (!drawing || event.pointerId !== drawing.pointerId) return;
  event.preventDefault();
  const [x, y] = eventPoint(event);
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
  updateGuideUI();
  updateLiveScore();
}

function repaintUserStrokes() {
  clearStudy();
  userStrokes.forEach((stroke) => paintStroke(ctx, stroke));
  updateGuideUI();
  updateLiveScore();
}

function prepareReferenceScore() {
  const scale = 96 / Math.max(recipe.width, recipe.height);
  const width = Math.max(1, Math.round(recipe.width * scale));
  const height = Math.max(1, Math.round(recipe.height * scale));
  referenceScoreCanvas.width = paintingScoreCanvas.width = width;
  referenceScoreCanvas.height = paintingScoreCanvas.height = height;
  const referenceCtx = referenceScoreCanvas.getContext("2d", { willReadFrequently: true });
  referenceCtx.drawImage($("reference-image"), 0, 0, width, height);
  referenceReady = true;
}

function updateLiveScore() {
  if (!referenceReady) return;
  const scoreCtx = paintingScoreCanvas.getContext("2d", { willReadFrequently: true });
  scoreCtx.drawImage(canvas, 0, 0, paintingScoreCanvas.width, paintingScoreCanvas.height);
  const a = referenceScoreCanvas.getContext("2d").getImageData(0, 0, referenceScoreCanvas.width, referenceScoreCanvas.height).data;
  const b = scoreCtx.getImageData(0, 0, paintingScoreCanvas.width, paintingScoreCanvas.height).data;
  let difference = 0;
  for (let i = 0; i < a.length; i += 4) difference += Math.abs(a[i] - b[i]) + Math.abs(a[i + 1] - b[i + 1]) + Math.abs(a[i + 2] - b[i + 2]);
  const similarity = Math.max(0, 100 * (1 - difference / (a.length / 4 * 3 * 255)));
  $("live-score").textContent = `${similarity.toFixed(1)}%`;
}

function buildStageButtons() {
  $("stage-buttons").replaceChildren(...boundaries.map((stage, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "stage-button";
    button.innerHTML = `<span>0${index + 1}</span>${stage.label}`;
    button.setAttribute("aria-label", `Show painting through ${stage.label}, ${stage.end} strokes`);
    button.addEventListener("click", () => setWatchCount(stage.end));
    return button;
  }));
}

function buildPalette() {
  const colours = [];
  const stride = Math.max(1, Math.floor(strokes.length / 80));
  for (let i = 0; i < strokes.length && colours.length < 6; i += stride) {
    if (!colours.includes(strokes[i].c)) colours.push(strokes[i].c);
  }
  $("recipe-palette").replaceChildren(...colours.map((colour) => {
    const dot = document.createElement("span");
    dot.className = "palette-dot";
    dot.style.background = colour;
    dot.title = colour;
    return dot;
  }));
}

async function load() {
  const id = new URLSearchParams(location.search).get("id");
  if (!id || !/^[a-z0-9-]+$/.test(id)) throw new Error("A valid painting id is required.");
  const [recipeResponse, manifestResponse] = await Promise.all([fetch(`../recipes/${id}.json`), fetch("../recipes/manifest.json")]);
  if (!recipeResponse.ok) throw new Error(`Recipe returned ${recipeResponse.status}`);
  recipe = await recipeResponse.json();
  if (manifestResponse.ok) {
    const manifest = await manifestResponse.json();
    const entry = manifest.find((item) => item.id === id);
    recipe.scores = entry?.scores;
    recipe.credit = entry?.credit || recipe.credit;
  }
  strokes = flattenStages(recipe);
  boundaries = boundariesFor(recipe);
  lessonMode = strokes.length < 1000;
  const minimumStrokes = lessonMode ? 1 : recipe.profile === "flat" ? 500 : id === "sunflowers" ? 2500 : 1500;
  if (strokes.length < minimumStrokes || strokes.length > 6000 || strokes.length !== recipe.strokeCount) throw new Error("This recipe has an invalid stroke budget.");
  document.title = `${recipe.title} — Painting Cookbook`;
  $("painting-title").textContent = recipe.title;
  $("artist-line").textContent = `${recipe.artist} · ${recipe.year}`;
  $("lesson-tip").hidden = !recipe.lessonTip;
  $("lesson-tip").textContent = recipe.lessonTip || "";
  $("recipe-score").textContent = recipe.scores?.similarity ?? "—";
  $("reference-progress").max = strokes.length;
  $("reference-image").src = recipe.reference || `../references/${id}.jpg`;
  $("reference-image").alt = `Original ${recipe.title} by ${recipe.artist}`;
  $("reference-caption").textContent = `${recipe.title}, ${recipe.artist}, ${recipe.year}. Original reference; not a painting layer.`;
  showReferenceCredit(recipe.credit);
  $("study-description").textContent = recipe.description || descriptions[id] || "A stroke-by-stroke study in layered colour and gesture.";
  $("stat-strokes").textContent = strokes.length.toLocaleString();
  $("scrubber").max = strokes.length;
  const defaultSpeed = Math.max(10, Math.min(500, Math.round(strokes.length / 20 / 10) * 10));
  $("speed").value = defaultSpeed;
  $("speed-output").textContent = `${defaultSpeed}/s`;
  canvas.width = guide.width = recipe.width;
  canvas.height = guide.height = recipe.height;
  frame.style.aspectRatio = `${recipe.width} / ${recipe.height}`;
  buildStageButtons();
  buildPalette();
  setWatchCount(0);
  $("study").hidden = false;
  try {
    await $("reference-image").decode();
    prepareReferenceScore();
  } catch {
    // Painting remains fully usable if only the optional live metric cannot load.
    $("live-score").textContent = "Unavailable";
  }
}

function showReferenceCredit(credit) {
  const element = $("reference-credit");
  element.replaceChildren();
  if (!credit) {
    element.hidden = true;
    return;
  }
  const photographic = credit.licence === "CC BY-SA 4.0";
  element.append(document.createTextNode(`${photographic ? "Photo by " : ""}${credit.author}, `));
  if (photographic) {
    const licence = document.createElement("a");
    licence.href = "https://creativecommons.org/licenses/by-sa/4.0/";
    licence.textContent = credit.licence;
    element.append(licence, document.createTextNode(", "));
  } else {
    element.append(document.createTextNode(`${credit.licence}, `));
  }
  const source = document.createElement("a");
  source.className = "reference-source";
  source.href = credit.url;
  source.textContent = `via ${credit.source || "Wikimedia Commons"}`;
  element.append(source);
  if (credit.note) element.append(document.createTextNode(`. ${credit.note}`));
  element.hidden = false;
}

$("watch-mode").addEventListener("click", () => setMode("watch"));
$("paint-mode").addEventListener("click", () => setMode("paint"));
$("play-button").addEventListener("click", playReplay);
$("speed").addEventListener("input", () => $("speed-output").textContent = `${$("speed").value}/s`);
$("scrubber").addEventListener("input", () => setWatchCount(Number($("scrubber").value)));
$("undo-button").addEventListener("click", () => {
  if (paintIndex > 0) {
    paintIndex -= 1;
    userStrokes.pop();
    repaintUserStrokes();
  }
});
$("skip-button").addEventListener("click", () => {
  if (mode !== "paint" || paintIndex >= strokes.length) return;
  const stage = boundaries.find((boundary) => paintIndex >= boundary.start && paintIndex < boundary.end);
  while (paintIndex < stage.end) {
    const stroke = strokes[paintIndex];
    paintStroke(ctx, stroke);
    userStrokes.push(stroke);
    paintIndex += 1;
  }
  updateGuideUI();
  updateLiveScore();
});
$("restart-button").addEventListener("click", () => {
  paintIndex = 0;
  userStrokes = [];
  drawing = null;
  repaintUserStrokes();
});
canvas.addEventListener("pointerdown", beginPaint);
canvas.addEventListener("pointermove", movePaint);
canvas.addEventListener("pointerup", finishPaint);
canvas.addEventListener("pointercancel", finishPaint);

load().catch((error) => {
  $("load-error").hidden = false;
  $("error-message").textContent = error.message;
});
