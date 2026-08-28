#!/usr/bin/env node

import { build } from "esbuild";
import { csvParse } from "d3-dsv";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { readFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const args = parseArgs(process.argv.slice(2));
if (!args.input || !args.config || !args.output) {
  console.error("Usage: npm run render -- --input DATA.csv --config CHART.json --output CHART.html");
  process.exit(2);
}

const here = path.dirname(fileURLToPath(import.meta.url));
const config = JSON.parse(await readFile(path.resolve(args.config), "utf8"));
const data = csvParse(await readFile(path.resolve(args.input), "utf8"));
validate(config, data);

const result = await build({
  entryPoints: [path.join(here, "src/runtime.ts")],
  bundle: true,
  write: false,
  format: "iife",
  platform: "browser",
  target: ["es2022"],
  minify: true,
  keepNames: true,
  define: {
    __CHART_CONFIG__: safeJson(config),
    __CHART_DATA__: safeJson(data),
  },
});

const javascript = result.outputFiles[0].text;
const output = path.resolve(args.output);
await mkdir(path.dirname(output), { recursive: true });
await writeFile(output, htmlDocument(config, javascript));
console.log(output);

function parseArgs(argv) {
  const values = {};
  for (let index = 0; index < argv.length; index += 2) {
    values[argv[index].replace(/^--/, "")] = argv[index + 1];
  }
  return values;
}

function validate(config, data) {
  const required = ["chart_type", "title", "subtitle", "source", "y"];
  if (config.chart_type !== "choropleth") required.push("x");
  for (const key of required) {
    if (!config[key]) throw new Error(`Missing config field: ${key}`);
  }
  if (!data.length) throw new Error("The input CSV is empty");
  const columns = config.chart_type === "choropleth"
    ? [config.region_key ?? config.x, config.y]
    : [config.x, config.y, config.series];
  for (const key of columns) {
    if (key && !(key in data[0])) throw new Error(`Missing CSV column: ${key}`);
  }
}

function safeJson(value) {
  return JSON.stringify(value).replaceAll("<", "\\u003c");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

// Base64 @font-face rules for the bundled Jost statics. Read synchronously
// at render time so the output HTML stays self-contained.
function jostFontFaces() {
  const fontsDir = path.join(here, "..", "assets", "fonts");
  const faces = [
    { family: "Jost Black", file: "Jost-Black.ttf", weight: 900 },
    { family: "Jost", file: "Jost-Regular.ttf", weight: 400 },
    { family: "Jost", file: "Jost-Medium.ttf", weight: 500 },
    { family: "Jost", file: "Jost-SemiBold.ttf", weight: 600 },
    { family: "Jost", file: "Jost-Bold.ttf", weight: 700 },
  ];
  return faces
    .map(({ family, file, weight }) => {
      const b64 = readFileSync(path.join(fontsDir, file)).toString("base64");
      return `@font-face{font-family:"${family}";font-style:normal;font-weight:${weight};font-display:swap;src:url(data:font/ttf;base64,${b64}) format("truetype")}`;
    })
    .join("");
}

function htmlDocument(config, javascript) {
  const note = config.note ? `<p class="note">${escapeHtml(config.note)}</p>` : "";
  // Choropleth charts embed the US state geometry (Census TIGER 5m,
  // simplified) as a global before the app bundle.
  const statesGlobal = config.chart_type === "choropleth"
    ? `<script>window.__US_STATES__ = ${readFileSync(path.join(here, "..", "assets", "us-states.geojson"), "utf8").replaceAll("<", "\\u003c")};</script>`
    : "";
  const headers = config.chart_type === "choropleth"
    ? [config.region_key ?? "region"]
    : [config.x];
  if (config.series && config.chart_type !== "choropleth") headers.push(config.series);
  headers.push(config.y);
  // When the chart carries CI bounds, expose them in the fallback
  // table so statistical claims ("CIs overlap") are reader-verifiable.
  if (config.ci_low && config.ci_high) {
    headers.push(config.ci_low, config.ci_high);
  }
  // Accessible table headers must be human-readable, not config keys.
  const headerLabels = new Map([
    ["income_band", "Income band"], ["poverty_band", "Income band"], ["stusps", "State"],
    ["state", "State"], ["group", "Group"], ["expansion_status", "Expansion status"],
    ["expansion", "Expansion status"], ["share", "Share"], ["gap_pts", "Gap (percentage points)"],
    ["delta_pts", "Change (percentage points)"], ["ratio", "Ratio"], ["pct_of_us", "% of US share of GDP"],
    ["deviation", "Deviation (GDP points)"], ["country", "Country"], ["region", "Region"],
    ["metric", "Metric"], ["rung", "Income rung"], ["share_of_gdp", "Share of GDP"],
    ["cost_barrier", "Cost-barrier share"], ["employer_coverage", "Employer coverage share"],
    ["ci_low", "Lower 95% CI"], ["ci_high", "Upper 95% CI"],
  ]);
  const labelFor = (h) => headerLabels.get(h) ?? h;
  const headerCells = headers.map((h) => `<th scope="col">${escapeHtml(labelFor(h))}</th>`).join("");
  // Editorial theme embeds Jost (Black for headline, Regular for body) so the
  // self-contained artifact carries its own fonts; default theme keeps the
  // system sans stack.
  // Bauhaus: primary colors + black/white, lowercase headline, black frame.
  // Swiss: native grotesque stack (Helvetica/Arial — Liberation Sans is
  // metric-compatible, so no embedding needed), monochrome + red accent,
  // flush-left with a red eyebrow above the headline.
  const isBauhaus = config.theme === "bauhaus";
  const isSwiss = config.theme === "swiss";
  const jostCss = config.theme === "editorial" || isBauhaus ? jostFontFaces() : "";
  const fontStack = config.theme === "editorial" || isBauhaus
    ? '"Jost", "Helvetica Neue", Arial, sans-serif'
    : isSwiss
      ? 'Helvetica, "Helvetica Neue", Arial, sans-serif'
      : 'Roboto, "Helvetica Neue", Arial, sans-serif';
  const headlineStack = config.theme === "editorial" || isBauhaus
    ? '"Jost Black", "Jost", "Helvetica Neue", Arial, sans-serif'
    : '"Roboto Condensed", Roboto, sans-serif';
  const headlineWeight = config.theme === "editorial" || isBauhaus ? 900 : isSwiss ? 700 : 800;
  const headlineTransform = isBauhaus ? "lowercase" : "none";
  const paper = config.theme === "editorial" ? "#f8f7f5" : isBauhaus ? "#faf9f6" : isSwiss ? "#ffffff" : "#fcfcfa";
  const ink = config.theme === "editorial" ? "#111111" : isBauhaus ? "#0a0a0a" : isSwiss ? "#111111" : "#17212b";
  const muted = config.theme === "editorial" ? "#333333" : isBauhaus ? "#8a8a8a" : isSwiss ? "#6e6e6e" : "#64717d";
  const rule = config.theme === "editorial" ? "#d9d9d9" : isBauhaus ? "#0a0a0a" : isSwiss ? "#d8d8d8" : "#d9dee2";
  const chartBorder = isBauhaus ? "1px solid #0a0a0a" : "none";
  const eyebrowHtml = isSwiss && config.eyebrow
    ? `<p class="eyebrow">${escapeHtml(config.eyebrow.toUpperCase())}</p>`
    : "";
  const eyebrowCss = isSwiss
    ? `.eyebrow{font-family:Helvetica,Arial,sans-serif;font-size:.8rem;font-weight:700;letter-spacing:.14em;color:${config.color ?? "#e30613"};margin:0 0 10px;text-transform:uppercase}`
    : "";
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(config.title)}</title>
<style>
${jostCss}
${eyebrowCss}
:root{color-scheme:light;--paper:${paper};--ink:${ink};--muted:${muted};--rule:${rule};--accent:${escapeHtml(config.color ?? "#008c95")}}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:${fontStack}}
main{max-width:1120px;margin:0 auto;padding:clamp(24px,5vw,64px)}
header{max-width:1040px;margin-bottom:28px}h1{font-family:${headlineStack};font-size:clamp(2rem,5vw,4rem);line-height:.98;letter-spacing:-.035em;margin:0 0 14px;font-weight:${headlineWeight};text-transform:${headlineTransform}}
.subtitle{font-size:clamp(1rem,2vw,1.35rem);line-height:1.4;color:var(--muted);margin:0}.chart{width:100%;min-height:430px;border:${chartBorder}}.chart svg{display:block;overflow:visible}
/* Scroll-reveal "unfold" — the plot's MARKS choreograph into place when the
   chart scrolls into view: bars grow from the baseline, dots pop, stems/arrows
   draw themselves, labels fade up, staggered so the chart "unfolds" like a
   premium editorial piece. Driven by the parent page via postMessage in the
   explorer; standalone charts arm it via their own IntersectionObserver.
   Everything is scoped under prefers-reduced-motion:no-preference and
   #chart.reveal-play, so the default state is fully visible (failsafe) and
   reduced-motion is instant. */
@media (prefers-reduced-motion: no-preference){
  #chart.reveal-play .anim-bar-v{opacity:0;transform:scaleY(0);transform-origin:bottom;transform-box:fill-box;animation:anim-bar .7s cubic-bezier(.22,1,.36,1) var(--d,0ms) forwards}
  #chart.reveal-play .anim-bar-h{opacity:0;transform:scaleX(0);transform-origin:left;transform-box:fill-box;animation:anim-bar .7s cubic-bezier(.22,1,.36,1) var(--d,0ms) forwards}
  #chart.reveal-play .anim-dot{opacity:0;transform:scale(0);transform-box:fill-box;animation:anim-dot .55s cubic-bezier(.34,1.56,.64,1) var(--d,0ms) forwards}
  #chart.reveal-play .anim-stem,#chart.reveal-play .anim-arrow{opacity:0;stroke-dasharray:1;stroke-dashoffset:1;animation:anim-draw .65s cubic-bezier(.22,1,.36,1) var(--d,0ms) forwards}
  #chart.reveal-play .anim-map{opacity:0;animation:anim-map .6s ease-out var(--d,0ms) forwards}
  #chart.reveal-play .anim-label{opacity:0;translate:0 6px;animation:anim-label .5s ease-out var(--d,0ms) forwards}
  @keyframes anim-bar{to{opacity:1;transform:scale(1)}}
  @keyframes anim-dot{to{opacity:1;transform:scale(1)}}
  @keyframes anim-draw{to{opacity:1;stroke-dashoffset:0}}
  @keyframes anim-map{to{opacity:1}}
  @keyframes anim-label{from{opacity:0;translate:0 6px}to{opacity:1;translate:0 0}}
}.meta{border-top:1px solid var(--rule);margin-top:24px;padding-top:14px;color:var(--muted);font-size:.84rem;line-height:1.45}.source,.note{margin:.2rem 0}
details{margin-top:24px;color:var(--muted)}summary{cursor:pointer;font-weight:700}table{border-collapse:collapse;width:100%;margin-top:12px;color:var(--ink)}th,td{text-align:left;padding:9px 8px;border-bottom:1px solid var(--rule)}
@media(max-width:520px){main{padding:22px 16px}h1{letter-spacing:-.025em}.chart{overflow-x:auto}.chart svg,.plot-figure svg{max-width:none!important}}
/* Mobile scroll affordance (runtime.ts injects .scroll-cue/.scroll-hint when
   the 480px legibility floor overflows the viewport). The cue is a positioned
   gradient overlay pinned to the right edge of the scroll container; the pill
   sits below the chart. Animation is gated under no-preference; reduced-motion
   users get the same elements but they vanish instantly on first scroll
   (remove()), with no transform/opacity transition at all. */
#chart{position:relative}
.scroll-cue{position:absolute;top:0;right:0;height:100%;width:56px;pointer-events:none;background:linear-gradient(to left,var(--paper) 20%,rgba(255,255,255,0));-webkit-mask-image:linear-gradient(to right,transparent,#000);mask-image:linear-gradient(to right,transparent,#000)}
.scroll-hint{margin-top:10px;text-align:center;font-size:.8rem;color:var(--muted);background:var(--paper);border:1px solid var(--rule);border-radius:999px;padding:6px 14px;width:max-content;margin-left:auto;margin-right:auto}
@media(prefers-reduced-motion:no-preference){
  .scroll-cue,.scroll-hint{animation:cue-fade-out .4s ease-out forwards}
}
@keyframes cue-fade-out{to{opacity:0}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;animation:none!important;transition:none!important}}
</style>
</head>
<body>
<main>
<header>${eyebrowHtml}<h1>${escapeHtml(config.title)}</h1><p class="subtitle">${escapeHtml(config.subtitle)}</p></header>
<div id="chart" class="chart" role="img" tabindex="0" aria-label="${escapeHtml(config.title)}. ${escapeHtml(config.subtitle)}"></div>
<div class="meta"><p class="source"><strong>Source:</strong> ${escapeHtml(config.source)}</p>${note}</div>
<details><summary>View underlying data</summary><table><caption>${escapeHtml(config.title)} — underlying data</caption><thead><tr>${headerCells}</tr></thead><tbody id="data-body"></tbody></table></details>
</main>
${statesGlobal}
<script>${javascript}</script>
</body>
</html>`;
}
