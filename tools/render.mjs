#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "/app/node_modules/playwright-core/index.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");

function usage() {
  console.error("Usage: node tools/render.mjs recipes/<id>.json [recipes/<id>.png] | --all");
  process.exitCode = 1;
}

const args = process.argv.slice(2);
let jobs = [];
if (args[0] === "--all") {
  jobs = fs.readdirSync(path.join(root, "recipes"))
    .filter((name) => name.endsWith(".json") && !name.endsWith(".score.json") && name !== "manifest.json")
    .map((name) => {
      const input = path.join(root, "recipes", name);
      return [input, input.replace(/\.json$/, ".png")];
    });
} else if (args[0]) {
  const input = path.resolve(args[0]);
  jobs = [[input, args[1] ? path.resolve(args[1]) : input.replace(/\.json$/, ".png")]];
} else {
  usage();
}

if (jobs.length) {
  const browser = await chromium.launch({ headless: true, args: ["--allow-file-access-from-files"] });
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.goto(`file://${path.join(here, "render-page.html")}`);
  await page.waitForFunction(() => window.rendererReady === true);

  for (const [input, output] of jobs) {
    const started = Date.now();
    const recipe = JSON.parse(fs.readFileSync(input, "utf8"));
    const dataURL = await page.evaluate((data) => window.renderRecipeToPNG(data), recipe);
    const png = Buffer.from(dataURL.split(",")[1], "base64");
    fs.writeFileSync(output, png);
    const count = recipe.strokes?.length || recipe.stages.reduce((sum, stage) => sum + stage.strokes.length, 0);
    console.log(JSON.stringify({ recipe: path.basename(input), output: path.relative(root, output), strokes: count, bytes: png.length, ms: Date.now() - started }));
  }
  await browser.close();
  if (errors.length) {
    console.error(errors.join("\n"));
    process.exitCode = 1;
  }
}
