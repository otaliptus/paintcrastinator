// Optional background music: a soft lo-fi loop made for Paintcrastinator (CC0).
// Off by default. The choice is remembered, and the loop continues roughly where it was
// when you move between pages. Web Audio is used so the loop is gapless.
const KEY = "paintcrastinator:music";
const button = document.getElementById("music-toggle");
let on = false;
try { on = localStorage.getItem(KEY) === "on"; } catch { /* storage blocked */ }
let offset = 0;
try { offset = Number(sessionStorage.getItem(`${KEY}:t`)) || 0; } catch { /* storage blocked */ }

let ctx, gain, buffer, source, startedAt = 0;

// Must run inside a click or key handler: browsers only allow sound after a user gesture.
function unlock() {
  ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
  if (ctx.state === "suspended") ctx.resume();
}

async function load() {
  if (buffer) return;
  // AAC first (Safari, Chrome); Opus if this browser cannot decode AAC (some Chromium builds).
  for (const file of ["lofi-loop.m4a", "lofi-loop.ogg"]) {
    try {
      const data = await (await fetch(file)).arrayBuffer();
      buffer = await ctx.decodeAudioData(data);
      break;
    } catch { /* try the next format */ }
  }
  if (!buffer) throw new Error("No playable music format");
  gain = ctx.createGain();
  gain.gain.value = 0;
  gain.connect(ctx.destination);
}

const position = () => (source && buffer ? (offset + ctx.currentTime - startedAt) % buffer.duration : offset);

async function play() {
  await load();
  if (source || !on) return;
  source = ctx.createBufferSource();
  source.buffer = buffer;
  source.loop = true;
  source.connect(gain);
  startedAt = ctx.currentTime;
  source.start(0, offset % buffer.duration);
  gain.gain.cancelScheduledValues(ctx.currentTime);
  gain.gain.setTargetAtTime(0.32, ctx.currentTime, 0.8); // gentle fade in
}

function stop() {
  if (!source) return;
  offset = position();
  const old = source;
  source = null;
  gain.gain.cancelScheduledValues(ctx.currentTime);
  gain.gain.setTargetAtTime(0, ctx.currentTime, 0.15);
  old.stop(ctx.currentTime + 0.7);
}

function render() {
  button.setAttribute("aria-pressed", String(on));
  button.textContent = on ? "♪ Music on" : "♪ Music off";
}

button.addEventListener("click", () => {
  on = !on;
  try { localStorage.setItem(KEY, on ? "on" : "off"); } catch { /* storage blocked */ }
  render();
  if (on) { unlock(); play().catch(() => {}); } else stop();
});

addEventListener("pagehide", () => {
  try { sessionStorage.setItem(`${KEY}:t`, String(position())); } catch { /* storage blocked */ }
});

render();
if (on) {
  // Music was left on: start it at the first click or key press on this page.
  const start = (event) => {
    if (event.target === button) return; // the button's own handler decides
    removeEventListener("pointerdown", start);
    removeEventListener("keydown", start);
    unlock();
    play().catch(() => {});
  };
  addEventListener("pointerdown", start);
  addEventListener("keydown", start);
}
