#!/usr/bin/env node
// Animation correctness audit for all analysis charts.
// Usage: node audit-animation.mjs [WIDTH|all|reduced] [ANALYSES_DIR]
//   WIDTH      - test one width (375/768/1280/1920) standalone
//   all        - test all 4 widths standalone (default)
//   reduced    - test reduced-motion standalone at all widths
// Exits 0 only if every assertion passes.

import { chromium } from "@playwright/test";
import { readdirSync, existsSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const defaultRoot = path.resolve(scriptDir, "../../analyses");
const root = path.resolve(process.argv[3] ?? defaultRoot);
const mode = process.argv[2] ?? "all";
const widths = [375, 768, 1280, 1920];
const chartNames = readdirSync(root, { withFileTypes: true })
  .filter((d) => d.isDirectory() && existsSync(path.join(root, d.name, "interactive.html")))
  .map((d) => d.name)
  .sort();

const browser = await chromium.launch({ headless: true });
const failures = [];
const results = []; // {tag, ok, detail}

function record(tag, ok, detail = "") {
  results.push({ tag, ok, detail });
}

function fail(tag, msg) {
  failures.push(`[${tag}] ${msg}`);
  record(tag, false, msg);
}

function pass(tag) {
  record(tag, true);
}

async function waitSettled(page, tag) {
  await page.evaluate(() => {
    return new Promise((resolve) => {
      const chart = document.querySelector("#chart");
      if (!chart) return resolve();
      if (chart.dataset.reveal === "played" && !chart.classList.contains("reveal-play")) return resolve();
      const onSettled = () => {
        chart.removeEventListener("chart-settled", onSettled);
        resolve();
      };
      chart.addEventListener("chart-settled", onSettled);
      window.setTimeout(() => {
        chart.removeEventListener("chart-settled", onSettled);
        resolve();
      }, 12000);
    });
  });
  // Ensure the state is as expected after settle.
  const ok = await page.evaluate(() => {
    const chart = document.querySelector("#chart");
    return {
      hasChart: !!chart,
      reveal: chart?.dataset?.reveal,
      hasRevealPlay: chart?.classList?.contains("reveal-play"),
      settled: chart?.__chartSettled === true,
    };
  });
  if (!ok.hasChart) return fail(tag, "#chart missing");
  if (ok.reveal !== "played") return fail(tag, `reveal=${ok.reveal} (expected played)`);
  if (ok.hasRevealPlay) return fail(tag, ".reveal-play class still present after settle");
  if (!ok.settled) return fail(tag, "__chartSettled not true");
}

async function assertMarksSettled(page, tag) {
  const report = await page.evaluate(async () => {
    const svg = document.querySelector("#chart svg") || document.querySelector("svg");
    if (!svg) return { error: "no svg" };
    // Sample a diverse set of data marks: rect, circle, path, line.
    const sample = Array.from(svg.querySelectorAll("rect, circle, path, line"))
      .filter((el) => {
        const fill = el.getAttribute("fill");
        if (el.tagName === "rect" && (fill === "none" || fill === "transparent")) return false;
        return true;
      })
      .slice(0, 20);
    if (sample.length === 0) return { ok: true, sampled: 0 };
    const snap = (el) => {
      const st = window.getComputedStyle(el);
      return {
        opacity: st.opacity,
        transform: st.transform,
        transformOrigin: st.transformOrigin,
        strokeDashoffset: st.strokeDashoffset,
      };
    };
    const a = sample.map(snap);
    await new Promise((r) => setTimeout(r, 300));
    const b = sample.map(snap);
    const stable = a.every((v, i) =>
      v.opacity === b[i].opacity &&
      v.transform === b[i].transform &&
      v.transformOrigin === b[i].transformOrigin &&
      v.strokeDashoffset === b[i].strokeDashoffset
    );
    return { ok: stable, sampled: sample.length, mismatches: stable ? 0 : sample.filter((_, i) =>
      a[i].opacity !== b[i].opacity || a[i].transform !== b[i].transform
    ).length };
  });
  if (report.error) return fail(tag, report.error);
  if (!report.ok) return fail(tag, `${report.mismatches}/${report.sampled} marks still animating after 300ms`);
}

async function assertAnimationRan(page, tag) {
  const report = await page.evaluate(() => {
    const chart = document.querySelector("#chart");
    if (!chart) return { error: "no chart" };
    // Any element that had an animation class applied should have had a
    // transition or animation property at some point. We can't observe past
    // animation, but we can check that marks were classified and the CSS
    // rules were available (the anim-* classes are still present on marks).
    const marks = Array.from(chart.querySelectorAll(".anim-bar-h, .anim-bar-v, .anim-dot, .anim-stem, .anim-arrow, .anim-map, .anim-label"));
    if (marks.length === 0) return { ok: false, detail: "no animated marks found" };
    // Verify the CSS rules are actually present for at least one class.
    const hasRules = Array.from(document.styleSheets).some((sheet) => {
      try {
        return Array.from(sheet.cssRules || []).some((rule) =>
          rule.cssText && rule.cssText.includes("anim-bar")
        );
      } catch { return false; }
    });
    return { ok: hasRules, animatedMarks: marks.length, hasRules };
  });
  if (report.error) return fail(tag, report.error);
  if (!report.ok) return fail(tag, report.detail || `animation CSS missing; ${report.animatedMarks} marked`);
}

async function testStandalone(width, reducedMotion = false) {
  const tagPrefix = reducedMotion ? `reduced-${width}` : `${width}`;
  for (const name of chartNames) {
    const tag = `${tagPrefix}/${name}`;
    const html = path.join(root, name, "interactive.html");
    const context = await browser.newContext({
      viewport: { width, height: 900 },
      reducedMotion: reducedMotion ? "reduce" : "no-preference",
    });
    const page = await context.newPage();
    const errs = [];
    page.on("pageerror", (e) => errs.push(`pageerror: ${e.message}`));
    page.on("console", (m) => { if (m.type() === "error") errs.push(`console: ${m.text()}`); });
    await page.goto(`file://${path.resolve(html)}`, { waitUntil: "load" });

    // For reduced motion, wait a short moment and check that no reveal-play was ever added
    // OR that it is removed immediately; we still honor the settle contract.
    if (reducedMotion) {
      // Wait up to 12s for chart-settled.
      await waitSettled(page, tag);
      // Check that marks are at final state immediately (or at least not mid-animation).
      const state = await page.evaluate(() => {
        const chart = document.querySelector("#chart");
        const svg = chart?.querySelector("svg");
        if (!svg) return { error: "no svg" };
        const firstMark = svg.querySelector("rect[fill]:not([fill='none']):not([fill='transparent']), circle, path[fill]:not([fill='none']):not([fill='transparent']), line");
        if (!firstMark) return { ok: true, noMarks: true };
        const st = window.getComputedStyle(firstMark);
        return {
          opacity: st.opacity,
          transform: st.transform,
          revealPlay: chart.classList.contains("reveal-play"),
        };
      });
      if (state.error) fail(tag, state.error);
      else if (state.revealPlay) fail(tag, "reveal-play still present under reduced motion");
      else if (Number(state.opacity) < 0.99) fail(tag, `reduced-motion mark opacity=${state.opacity} (should be 1)`);
    } else {
      await waitSettled(page, tag);
      await assertMarksSettled(page, tag);
      await assertAnimationRan(page, tag);
    }

    for (const e of errs) fail(tag, e);
    if (!failures.some(f => f.startsWith(`[${tag}]`))) pass(tag);
    await context.close();
  }
}

// Main dispatch
if (mode === "all") {
  for (const w of widths) await testStandalone(w);
} else if (mode === "reduced") {
  for (const w of widths) await testStandalone(w, true);
} else if (/^\d+$/.test(mode)) {
  const w = Number(mode);
  if (!widths.includes(w)) { console.error("Unknown width", w); process.exit(2); }
  await testStandalone(w);
} else {
  console.error("Unknown mode:", mode);
  process.exit(2);
}

await browser.close();

// Print per-chart pass/fail table grouped by width/mode.
const groups = new Map();
for (const r of results) {
  const [mode, chart] = r.tag.includes("/") ? r.tag.split("/") : [r.tag, ""];
  if (!groups.has(mode)) groups.set(mode, []);
  groups.get(mode).push({ chart, ok: r.ok, detail: r.detail });
}
for (const [mode, charts] of groups) {
  console.log(`\n=== ${mode} ===`);
  for (const c of charts) {
    console.log(`  ${c.ok ? "PASS" : "FAIL"} ${c.chart}${c.detail ? " — " + c.detail : ""}`);
  }
}

console.log(failures.length === 0 ? "\nALL PASS" : `\nFAILURES (${failures.length}):`);
failures.slice(0, 80).forEach((f) => console.log(" ", f));
process.exit(failures.length ? 1 : 0);
