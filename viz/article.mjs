#!/usr/bin/env node
// Build a prose-and-charts article page from a Markdown brief and a set of
// interactive chart HTML files.
//
// Usage:
//   node viz/article.mjs OUT.html PROSE.md "Label|path/to/interactive.html" [...]
//
// The prose Markdown may contain `<!-- CHART: Label -->` markers; each marker
// is replaced by an embedded iframe holding the matching chart's interactive
// HTML. Iframes auto-size to their content (srcdoc is same-origin, so the
// parent can measure scrollHeight after load and on resize), so source notes
// and the x axis are always visible without scrolling inside the card.

import { readFile, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const [outputArg, proseArg, ...pairs] = process.argv.slice(2);
if (!outputArg || !proseArg || pairs.length === 0) {
  console.error('Usage: article.mjs OUT.html PROSE.md "Label|interactive.html" [...]');
  process.exit(2);
}

function escapeAttr(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

// Minimal, safe Markdown subset: ATX headings, bold, italic, inline code,
// paragraphs, thematic breaks, and blockquotes. Deliberately not a full
// CommonMark renderer — the briefs are authored to this subset.
function mdToHtml(markdown) {
  const lines = markdown.split(/\r?\n/);
  const out = [];
  let para = [];
  const flush = () => {
    if (para.length) {
      out.push(`<p>${para.join(" ")}</p>`);
      para = [];
    }
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) {
      flush();
      continue;
    }
    const h = line.match(/^(#{1,3})\s+(.*)$/);
    if (h) {
      flush();
      const level = h[1].length;
      out.push(`<h${level}>${inline(h[2])}</h${level}>`);
      continue;
    }
    if (/^\s*---+\s*$/.test(line)) {
      flush();
      out.push("<hr>");
      continue;
    }
    const q = line.match(/^>\s?(.*)$/);
    if (q) {
      flush();
      out.push(`<blockquote>${inline(q[1])}</blockquote>`);
      continue;
    }
    // Chart marker lines are replaced with figures AFTER markdown conversion,
    // so leave them as a single-token paragraph here.
    const marker = line.match(/^<!--\s*CHART:\s*(.*?)\s*-->$/);
    if (marker) {
      flush();
      out.push(`<p data-chart-marker="${marker[1].replaceAll('"', "&quot;")}"></p>`);
      continue;
    }
    para.push(inline(line));
  }
  flush();
  return out.join("\n");
}

function inline(text) {
  let s = escapeHtml(text);
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  return s;
}

const prose = await readFile(proseArg, "utf8");

// Load every chart once, keyed by label.
const charts = new Map();
for (const pair of pairs) {
  const sep = pair.indexOf("|");
  const label = pair.slice(0, sep);
  const file = pair.slice(sep + 1);
  charts.set(label, await readFile(file, "utf8"));
}

// Convert markdown first (chart markers become data-chart-marker paragraphs),
// then replace those placeholders with figure embeds. Replacing after
// conversion avoids escaping the generated HTML through the markdown pipeline.
const html = mdToHtml(prose);
let figureIndex = 0;
const body = html.replace(
  /<p data-chart-marker="([^"]*)"><\/p>/g,
  (whole, label) => {
    const htmlChart = charts.get(label);
    if (!htmlChart) {
      return `<!-- MISSING CHART: ${label} -->`;
    }
    figureIndex += 1;
    return (
      `<figure class="chart-embed" id="fig-${figureIndex}">` +
      `<iframe title="${escapeAttr(label)}" srcdoc="${escapeAttr(htmlChart)}"></iframe>` +
      `<figcaption>Figure ${figureIndex} — ${escapeAttr(label)}</figcaption>` +
      `</figure>`
    );
  }
);

if (body.includes("MISSING CHART")) {
  console.error(`article.mjs: prose references a chart that was not supplied:\n${body.match(/<!-- MISSING CHART: ([^>]+) -->/g)?.join("\n")}`);
  process.exit(3);
}

const page = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeAttr(prose.match(/^#\s+(.+)$/m)?.[1] ?? "Microdata Lab")}</title>
<style>
  :root{--paper:#ffffff;--ink:#111111;--muted:#6e6e6e;--rule:#d8d8d8;--red:#e30613}
  *{box-sizing:border-box}
  body{margin:0;background:var(--paper);color:var(--ink);font-family:Helvetica,"Helvetica Neue",Arial,sans-serif;line-height:1.6}
  article{max-width:760px;margin:0 auto;padding:clamp(28px,6vw,72px) clamp(20px,5vw,40px)}
  h1{font-size:clamp(1.9rem,5vw,3rem);line-height:1.05;letter-spacing:-.02em;margin:0 0 8px}
  h2{font-size:1.25rem;letter-spacing:-.01em;margin:2.2em 0 .6em}
  h3{font-size:1.05rem;margin:1.8em 0 .4em}
  p{margin:0 0 1.15em}
  hr{border:0;border-top:1px solid var(--rule);margin:2.2em 0}
  blockquote{border-left:3px solid var(--red);margin:1.2em 0;padding:0.2em 0 0.2em 1.1em;color:var(--muted)}
  code{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.9em;background:#f4f4f4;padding:1px 5px;border-radius:3px}
  figure.chart-embed{margin:2em 0}
  figure.chart-embed iframe{width:100%;border:1px solid var(--rule);border-radius:4px;display:block;min-height:480px}
  figcaption{color:var(--muted);font-size:.82rem;margin-top:8px;letter-spacing:.02em}
  .source-note{border-top:1px solid var(--rule);margin-top:3em;padding-top:1.2em;color:var(--muted);font-size:.85rem}
</style>
</head>
<body>
<article>
${body}
<p class="source-note">All figures use official sources processed through the immutable microdata pipeline. Hover charts for values; click "View underlying data" to expand each table.</p>
</article>
<script>
  // Auto-size each embedded iframe to its content so source notes and the x
  // axis are never clipped. srcdoc iframes are same-origin, so the parent can
  // read scrollHeight after load and on window resize.
  function fitFrame(frame) {
    try {
      const doc = frame.contentDocument;
      if (!doc || !doc.documentElement) return;
      const h = doc.documentElement.scrollHeight;
      if (h > 0) frame.style.height = h + "px";
    } catch (err) {
      // Cross-origin guard; srcdoc frames are same-origin so this is a no-op
      // safety net.
    }
  }
  const frames = Array.from(document.querySelectorAll("figure.chart-embed iframe"));
  for (const frame of frames) {
    frame.addEventListener("load", () => {
      fitFrame(frame);
      // Plot renders asynchronously; re-measure once fonts/layout settle.
      setTimeout(() => fitFrame(frame), 150);
      setTimeout(() => fitFrame(frame), 600);
    });
  }
  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => frames.forEach(fitFrame), 120);
  });
</script>
</body>
</html>`;

const output = path.resolve(outputArg);
await mkdir(path.dirname(output), { recursive: true });
await writeFile(output, page);
console.log(output);
