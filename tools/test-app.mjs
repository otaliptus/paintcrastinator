#!/usr/bin/env node
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { chromium } from "/app/node_modules/playwright-core/index.mjs";

const base = process.env.APP_URL || "http://127.0.0.1:4173/app";
const out = path.resolve("verification");
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ headless: true });
const errors = [];
const checks = [];

function watch(page) {
  page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
  page.on("console", (message) => { if (message.type() === "error") errors.push(`console: ${message.text()}`); });
}

async function counter(page) {
  const text = await page.locator("#stroke-counter").textContent();
  return Number(text.split("/")[0].trim().replaceAll(",", ""));
}

async function loadAllCards(page) {
  const cards = page.locator(".painting-card");
  for (let index = 0; index < await cards.count(); index += 1) await cards.nth(index).scrollIntoViewIfNeeded();
  await page.waitForFunction(() => [...document.querySelectorAll(".card-image")].every((image) => image.complete && image.naturalWidth > 0));
  await page.evaluate(() => scrollTo(0, 0));
}

const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
watch(page);
await page.goto(`${base}/index.html`, { waitUntil: "networkidle" });
assert.equal(await page.locator(".painting-card").count(), 10);
assert.equal(await page.locator(".shelf").count(), 2);
assert.equal(await page.locator("#masterworks-gallery .painting-card").count(), 5);
assert.equal(await page.locator("#icons-gallery .painting-card").count(), 5);
assert.equal(await page.locator("#icons-heading").textContent(), "Icons");
const manifest = JSON.parse(fs.readFileSync("recipes/manifest.json", "utf8"));
const expectedTotal = manifest.reduce((sum, recipe) => sum + recipe.strokeCount, 0);
assert.equal(await page.locator("#stroke-total").textContent(), expectedTotal.toLocaleString());
assert.match(await page.locator('meta[name="description"]').getAttribute("content"), /a car, two film stars, a painting and the Earth/);
await loadAllCards(page);
assert.equal(await page.locator(".card-image").evaluateAll((images) => images.every((image) => image.complete && image.naturalWidth > 0)), true);
checks.push("two shelves, ten library cards, dynamic stroke total and all offline thumbnails loaded");
await page.locator(".original-toggle").first().click();
assert.match(await page.locator(".card-image").first().getAttribute("src"), /references\/mona-lisa\.jpg$/);
await page.locator(".original-toggle").first().click();
assert.match(await page.locator(".card-image").first().getAttribute("src"), /recipes\/mona-lisa\.png$/);
checks.push("explicit library original toggle restores rendered thumbnail");
await page.screenshot({ path: path.join(out, "library-desktop.png"), fullPage: true });

await page.goto(`${base}/recipe.html?id=mona-lisa`, { waitUntil: "networkidle" });
await page.locator("#study").waitFor({ state: "visible" });
assert.equal(await page.locator("#painting-canvas").getAttribute("width"), "960");
assert.equal(await counter(page), 0);
assert.equal(await page.locator("#top-stroke-counter").textContent(), "0 / 5,000 strokes");
assert.equal(await page.locator("#reference-stage").textContent(), "Blank canvas");
assert.equal(await page.locator("#stage-buttons button").count(), 4);
checks.push("recipe starts blank with top-bar and reference-panel progress");
await page.locator("#play-button").click();
await page.waitForTimeout(300);
await page.locator("#play-button").click();
assert.ok(await counter(page) > 0 && await counter(page) < 5000);
checks.push("watch replay advances and pauses");
await page.locator("#stage-buttons button").first().click();
assert.equal(await counter(page), 420);
checks.push("stage scrubber lands exactly on blocking-in boundary");
await page.locator("#scrubber").evaluate((input) => { input.value = input.max; input.dispatchEvent(new Event("input", { bubbles: true })); });
assert.equal(await counter(page), 5000);
checks.push("continuous scrubber restores the finished painting");

await page.locator("#paint-mode").click();
assert.equal(await counter(page), 0);
assert.equal(await page.locator("#watch-controls").isVisible(), false);
assert.equal(await page.locator("#paint-controls").isVisible(), true);
const firstStroke = JSON.parse(fs.readFileSync("recipes/mona-lisa.json", "utf8")).stages[0].strokes[0];
const bounds = await page.locator("#painting-canvas").boundingBox();
const point = (x, y) => ({ x: bounds.x + x / 960 * bounds.width, y: bounds.y + y / 1431 * bounds.height });
const start = point(firstStroke.p[0], firstStroke.p[1]);
const end = point(firstStroke.p.at(-2), firstStroke.p.at(-1));
await page.mouse.move(start.x, start.y);
await page.mouse.down();
await page.mouse.move(end.x, end.y, { steps: 14 });
await page.mouse.up();
assert.equal(await counter(page), 1);
assert.notEqual(await page.locator("#live-score").textContent(), "—");
checks.push("pointer painting records one recipe-colour/size stroke and updates live colour match");
await page.locator("#undo-button").click();
assert.equal(await counter(page), 0);
await page.locator("#restart-button").click();
assert.equal(await counter(page), 0);
await page.mouse.click(start.x, start.y);
await page.locator("#skip-button").click();
assert.equal(await counter(page), 420);
assert.equal(await page.locator("#reference-stage").textContent(), "Form and color");
await page.locator("#restart-button").click();
assert.equal(await counter(page), 0);
checks.push("undo/restart reset painting; finish-stage auto-paints exactly to the next boundary");
await page.screenshot({ path: path.join(out, "recipe-desktop.png"), fullPage: true });

await page.goto(`${base}/recipe.html?id=countach`, { waitUntil: "networkidle" });
await page.locator("#study").waitFor({ state: "visible" });
const countach = JSON.parse(fs.readFileSync("recipes/countach.json", "utf8"));
const countachTotal = countach.strokeCount;
const countachLabel = `0 / ${countachTotal.toLocaleString()} strokes`;
assert.equal(await page.locator("#stroke-counter").textContent(), countachLabel);
assert.equal(await page.locator("#top-stroke-counter").textContent(), countachLabel);
assert.equal(await page.locator("#scrubber").getAttribute("max"), String(countachTotal));
assert.equal(await page.locator("#reference-progress").getAttribute("max"), String(countachTotal));
const defaultSpeed = Number(await page.locator("#speed").inputValue());
assert.ok(countachTotal / defaultSpeed >= 18 && countachTotal / defaultSpeed <= 23);
assert.equal(await page.locator("#reference-credit").isVisible(), true);
assert.match(await page.locator("#reference-credit").textContent(), /Photo by Palauenc05, CC BY-SA 4\.0, via Wikimedia Commons/);
assert.match(await page.locator("#reference-credit .reference-source").getAttribute("href"), /commons\.wikimedia\.org\/wiki\/File:Lamborghini_Countach/);
assert.ok(await page.locator("#reference-credit a[href*='creativecommons.org/licenses/by-sa/4.0']").count() === 1);
checks.push("car recipe uses its variable counter, scrubber, progress, 20-second default speed and visible linked attribution");
await page.locator("#play-button").click();
await page.waitForTimeout(300);
await page.locator("#play-button").click();
assert.ok(await counter(page) > 0 && await counter(page) < countachTotal);
await page.locator("#paint-mode").click();
await page.locator("#skip-button").click();
assert.equal(await counter(page), countach.stages[0].strokes.length);
await page.locator("#restart-button").click();
await page.locator("#watch-mode").click();
await page.locator("#stage-buttons button").first().click();
assert.equal(await counter(page), countach.stages[0].strokes.length);
await page.locator("#scrubber").evaluate((input) => { input.value = input.max; input.dispatchEvent(new Event("input", { bubbles: false })); });
assert.equal(await counter(page), countachTotal);
assert.equal(await page.locator("#top-stroke-counter").textContent(), `${countachTotal.toLocaleString()} / ${countachTotal.toLocaleString()} strokes`);
await page.screenshot({ path: path.join(out, "recipe-countach-desktop.png"), fullPage: true });
checks.push("variable-budget replay, finish-stage, exact stage boundary and full scrub reach the new recipe total");

for (const id of ["girl-with-a-pearl-earring", "starry-night", "great-wave", "van-gogh-self-portrait", "breakfast-at-tiffanys", "marilyn-1953", "the-scream", "blue-marble"]) {
  await page.goto(`${base}/recipe.html?id=${id}`, { waitUntil: "networkidle" });
  await page.locator("#study").waitFor({ state: "visible" });
  assert.equal(await counter(page), 0);
  assert.equal(await page.locator("#reference-image").evaluate((image) => image.complete && image.naturalWidth > 0), true);
}
checks.push("all ten recipe pages render with references and no missing data");
await page.goto(`${base}/recipe.html?id=the-scream`, { waitUntil: "networkidle" });
await page.locator("#study").waitFor({ state: "visible" });
const screamTotal = JSON.parse(fs.readFileSync("recipes/the-scream.json", "utf8")).strokeCount;
assert.equal(await page.locator("#reference-credit").textContent(), "Edvard Munch, Public domain, via Wikimedia Commons");
await page.locator("#scrubber").evaluate((input) => { input.value = input.max; input.dispatchEvent(new Event("input", { bubbles: false })); });
assert.equal(await counter(page), screamTotal);
await page.screenshot({ path: path.join(out, "recipe-the-scream-desktop.png"), fullPage: true });
checks.push("The Scream carries public-domain credit and its desktop study reaches the selected budget");

const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
watch(mobile);
await mobile.goto(`${base}/index.html`, { waitUntil: "networkidle" });
assert.equal(await mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
await loadAllCards(mobile);
await mobile.screenshot({ path: path.join(out, "library-mobile.png"), fullPage: true });
await mobile.goto(`${base}/recipe.html?id=marilyn-1953`, { waitUntil: "networkidle" });
await mobile.locator("#study").waitFor({ state: "visible" });
assert.equal(await mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
const marilynTotal = JSON.parse(fs.readFileSync("recipes/marilyn-1953.json", "utf8")).strokeCount;
assert.equal(await mobile.locator("#stroke-counter").textContent(), `0 / ${marilynTotal.toLocaleString()} strokes`);
await mobile.locator("#scrubber").evaluate((input) => { input.value = input.max; input.dispatchEvent(new Event("input", { bubbles: false })); });
assert.equal(await counter(mobile), marilynTotal);
await mobile.screenshot({ path: path.join(out, "recipe-marilyn-mobile.png"), fullPage: true });
await mobile.locator("#paint-mode").tap();
const canvasBox = await mobile.locator("#painting-canvas").boundingBox();
await mobile.touchscreen.tap(canvasBox.x + canvasBox.width / 2, canvasBox.y + canvasBox.height / 2);
assert.equal(await counter(mobile), 1);
checks.push("mobile library/Marilyn study have no horizontal overflow, variable total reaches N, and touch painting works");

await browser.close();
assert.deepEqual(errors, []);
checks.push("zero console errors and zero uncaught page errors throughout");
console.log(`PASS — ${checks.length} checks`);
for (const check of checks) console.log(`  ✓ ${check}`);
