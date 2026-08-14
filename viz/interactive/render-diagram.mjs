#!/usr/bin/env node

import { chromium } from "@playwright/test";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [htmlInput, pngOutput, scaleInput = "2"] = process.argv.slice(2);
if (!htmlInput || !pngOutput) {
  throw new Error("Usage: render-diagram.mjs DIAGRAM.html OUTPUT.png [SCALE]");
}
const scale = Number(scaleInput);
if (!Number.isFinite(scale) || scale < 1 || scale > 4) {
  throw new Error("SCALE must be between 1 and 4");
}
const htmlPath = path.resolve(htmlInput);
const source = await readFile(htmlPath, "utf8");
const match = source.match(/viewBox=["']0\s+0\s+([\d.]+)\s+([\d.]+)["']/i);
if (!match) throw new Error("Diagram needs a 0 0 W H viewBox");
const width = Math.ceil(Number(match[1]));
const height = Math.ceil(Number(match[2]));

const browser = await chromium.launch({ headless: true });
const errors = [];
try {
  const page = await browser.newPage({
    viewport: { width, height },
    deviceScaleFactor: scale,
  });
  page.on("pageerror", (error) => errors.push(`page error: ${error.message}`));
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      errors.push(`console ${message.type()}: ${message.text()}`);
    }
  });
  await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  const svg = page.locator("svg[role=img]").first();
  await svg.waitFor({ state: "visible" });
  const geometry = await svg.evaluate((node) => {
    const viewBox = node.viewBox.baseVal;
    const outside = [];
    for (const element of node.querySelectorAll("text, [data-node], [data-callout]")) {
      const box = element.getBBox();
      if (
        box.x < viewBox.x - 0.5 ||
        box.y < viewBox.y - 0.5 ||
        box.x + box.width > viewBox.x + viewBox.width + 0.5 ||
        box.y + box.height > viewBox.y + viewBox.height + 0.5
      ) {
        outside.push(element.id || element.textContent?.trim() || element.tagName);
      }
    }
    return {
      outside,
      clientWidth: node.getBoundingClientRect().width,
      clientHeight: node.getBoundingClientRect().height,
    };
  });
  if (geometry.outside.length) errors.push(`elements outside viewBox: ${geometry.outside.join(", ")}`);
  if (Math.abs(geometry.clientWidth / geometry.clientHeight - width / height) > 0.001) {
    errors.push("rendered SVG aspect ratio differs from viewBox");
  }
  if (errors.length) throw new Error(errors.join("\n"));
  await svg.screenshot({ path: path.resolve(pngOutput), omitBackground: false });
} finally {
  await browser.close();
}
console.log(path.resolve(pngOutput));
