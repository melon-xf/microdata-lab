#!/usr/bin/env node

import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [htmlInput, outputInput] = process.argv.slice(2);
if (!htmlInput || !outputInput) {
  throw new Error("Usage: screenshot.mjs CHART.html OUTPUT_DIR");
}

const htmlPath = path.resolve(htmlInput);
const outputDir = path.resolve(outputInput);
await mkdir(outputDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const errors = [];
try {
  for (const width of [375, 768, 1280, 1920]) {
    const page = await browser.newPage({ viewport: { width, height: 900 }, deviceScaleFactor: 1 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    page.on("pageerror", (error) => errors.push(`${width}px page error: ${error.message}`));
    page.on("console", (message) => {
      if (["error", "warning"].includes(message.type())) {
        errors.push(`${width}px console ${message.type()}: ${message.text()}`);
      }
    });
    await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "load" });
    // The main plot is the svg with class "plot-<hash>"; legend swatches are
    // small unclassed svgs inside spans and must be excluded. Bar charts
    // render the plot svg directly under #chart (no figure wrapper).
    await page
      .locator('#chart figure svg[class^="plot-"], #chart > svg[class^="plot-"]')
      .first()
      .waitFor({ state: "visible" });
    // The accessible fallback table is intentionally collapsed inside
    // <details> in the normal artifact. Attach first, then open it for QA so
    // this check tests the real accessibility path instead of timing out on
    // a correctly hidden table.
    const table = page.locator("table").first();
    await table.waitFor({ state: "attached" });
    const details = page.locator("details").first();
    if (await details.count()) {
      await details.evaluate((node) => {
        if (node instanceof HTMLDetailsElement) node.open = true;
      });
    }
    await table.waitFor({ state: "visible" });
    await page.locator(".source").waitFor({ state: "visible" });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    if (overflow) errors.push(`${width}px document overflow`);
    await page.keyboard.press("Tab");
    const chartFocused = await page.locator("#chart").evaluate((node) => node === document.activeElement);
    if (!chartFocused) errors.push(`${width}px chart is not keyboard focusable`);
    await page.screenshot({ path: path.join(outputDir, `interactive-${width}.png`), fullPage: true });
    await page.close();
  }
} finally {
  await browser.close();
}

if (errors.length > 0) {
  throw new Error(errors.join("\n"));
}
console.log(`Wrote responsive screenshots to ${outputDir}`);
