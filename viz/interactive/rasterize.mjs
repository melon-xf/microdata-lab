#!/usr/bin/env node
/**
 * Rasterize a chart HTML to a high-DPI PNG using headless Playwright.
 *
 * Usage:
 *   node rasterize.mjs --input chart.html --output figure.png [--scale 2]
 *
 * The PNG is produced from the SAME HTML/SVG that powers the interactive
 * chart, guaranteeing identical layout, colors, labels, and geometry.
 * No separate renderer, no drift.
 */
import { chromium } from "@playwright/test";
import { readFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const args = parseArgs(process.argv.slice(2));
if (!args.input || !args.output) {
  console.error("Usage: node rasterize.mjs --input chart.html --output figure.png [--scale 2]");
  process.exit(2);
}

const scale = parseFloat(args.scale ?? "2");
const width = parseInt(args.width ?? "1120");
const height = parseInt(args.height ?? "0"); // 0 = auto-fit to content

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({
  viewport: { width, height: height || 800 },
  deviceScaleFactor: scale,
});

const absInput = path.resolve(args.input);
await page.goto(`file://${absInput}`, { waitUntil: "networkidle" });

// Wait for the chart SVG to render
await page.waitForSelector("svg", { timeout: 15000 });

// Wait for the scroll-reveal animation to finish (if any): the runtime
// dispatches "chart-settled" when the reveal completes or is skipped
// (reduced-motion, or the 1.6s failsafe), so the PNG never captures a
// half-animated frame.
const settled = await page.evaluate(() => new Promise((resolve) => {
  const chart = document.querySelector("#chart");
  if (!chart) return resolve(true);
  let done = false;
  const finish = () => { if (!done) { done = true; resolve(true); } };
  if (chart.dataset.reveal === "played" && !chart.classList.contains("reveal-play")) {
    return finish(); // already settled before we attached
  }
  chart.addEventListener("chart-settled", finish, { once: true });
  setTimeout(finish, 12000); // failsafe: long enough for 50-dot strips (4b)
}));
if (!settled) throw new Error("chart-settled never fired");

// Auto-fit: measure the actual content height (header + chart + footer)
let actualHeight = height;
if (!height) {
  actualHeight = await page.evaluate(() => {
    const main = document.querySelector("main");
    return main ? main.scrollHeight + 80 : document.body.scrollHeight;
  });
  await page.setViewportSize({ width, height: actualHeight });
}

// Reflow after potential resize
await page.waitForTimeout(300);

const absOutput = path.resolve(args.output);
await page.screenshot({
  path: absOutput,
  fullPage: true,
  omitBackground: false,
});

await browser.close();
console.log(absOutput);

function parseArgs(argv) {
  const values = {};
  for (let i = 0; i < argv.length; i += 2) {
    values[argv[i].replace(/^--/, "")] = argv[i + 1];
  }
  return values;
}
