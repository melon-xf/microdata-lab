#!/usr/bin/env node
// Playwright DOM audit for SVG label clipping.
// Usage: node audit-labels.mjs CHART.html WIDTH
// Exit 0 if every text element in every SVG inside the chart is within its
// SVG viewBox with 2px tolerance. Observable Plot axis titles may use up to
// 12px of intentional visible overflow; all other labels remain strict.

import { chromium } from "@playwright/test";
import process from "node:process";
import path from "node:path";

const file = process.argv[2];
const widthArg = process.argv[3];
if (!file || !widthArg) {
  console.error("Usage: audit-labels.mjs CHART.html WIDTH");
  process.exit(2);
}
const width = Number(widthArg);
if (!Number.isFinite(width) || width <= 0) {
  console.error("Invalid width");
  process.exit(2);
}

const htmlPath = path.resolve(file);

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width, height: 900 } });
try {
  await page.goto(`file://${htmlPath}`, { waitUntil: "networkidle" });
  // Wait for the chart to settle. The runtime dispatches a CustomEvent
  // "chart-settled" on #chart after reveal (or reduced-motion skip). If the
  // event has already fired, resolve immediately.
  await page.evaluate(() => {
    return new Promise((resolve) => {
      const chart = document.querySelector("#chart");
      if (!chart) return resolve();
      if (chart.__chartSettled) return resolve();
      const onSettled = () => {
        chart.removeEventListener("chart-settled", onSettled);
        resolve();
      };
      chart.addEventListener("chart-settled", onSettled);
      // Charts with many marks (e.g. 4b strip with 50 dots) take >5s to
      // settle; give a generous fallback so the audit never races animation.
      window.setTimeout(() => {
        chart.removeEventListener("chart-settled", onSettled);
        resolve();
      }, 15000);
    });
  });
  await new Promise((r) => setTimeout(r, 100));
  const report = await page.evaluate(() => {
    const svgEls = Array.from(document.querySelectorAll("svg"));
    const results = [];
    let pass = true;
    const tolerance = 2;

    for (const svg of svgEls) {
      const ctm = svg.getScreenCTM();
      if (!ctm) continue;
      const inv = ctm.inverse();
      const vb = svg.viewBox.baseVal;
      const svgPass = { svg: true, viewBox: { x: vb.x, y: vb.y, width: vb.width, height: vb.height }, labels: [] };
      const texts = Array.from(svg.querySelectorAll("text"));
      for (const text of texts) {
        const t = (text.textContent || "").trim();
        if (!t) continue;
        const bb = text.getBoundingClientRect();
        const p1 = svg.createSVGPoint();
        p1.x = bb.left;
        p1.y = bb.top;
        const p2 = svg.createSVGPoint();
        p2.x = bb.right;
        p2.y = bb.bottom;
        const loc1 = p1.matrixTransform(inv);
        const loc2 = p2.matrixTransform(inv);
        const minX = Math.min(loc1.x, loc2.x);
        const maxX = Math.max(loc1.x, loc2.x);
        const minY = Math.min(loc1.y, loc2.y);
        const maxY = Math.max(loc1.y, loc2.y);
        const isAxisTitle = text.closest('g[aria-label$="-axis label"]') !== null;
        const visibleOverflow = getComputedStyle(svg).overflow === "visible";
        const labelTolerance = isAxisTitle && visibleOverflow ? 12 : tolerance;
        const inside =
          minX >= vb.x - labelTolerance &&
          maxX <= vb.x + vb.width + labelTolerance &&
          minY >= vb.y - labelTolerance &&
          maxY <= vb.y + vb.height + labelTolerance;
        if (!inside) pass = false;
        svgPass.labels.push({
          text: t.slice(0, 120),
          minX: Math.round(minX * 100) / 100,
          maxX: Math.round(maxX * 100) / 100,
          minY: Math.round(minY * 100) / 100,
          maxY: Math.round(maxY * 100) / 100,
          tolerance: labelTolerance,
          inside,
        });
      }
      results.push(svgPass);
    }
    return { pass, width: window.innerWidth, svgs: results };
  });

  report.file = htmlPath;
  report.width = width;
  const failed = report.svgs.flatMap((s, i) =>
    s.labels.filter((l) => !l.inside).map((l) => ({ svgIndex: i, ...l }))
  );
  report.failed = failed;

  console.log(JSON.stringify(report, null, 2));
  await browser.close();
  process.exit(report.pass ? 0 : 1);
} catch (err) {
  console.error(err.message || err);
  await browser.close();
  process.exit(3);
}
