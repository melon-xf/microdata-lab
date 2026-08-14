// ──────────────────────────────────────────────────────────────────────
// QA Layer — deterministic post-render checks.
// Runs after Plot renders the SVG. Fails loudly (throws) on issues that
// vision-model QA kept catching manually.
// ──────────────────────────────────────────────────────────────────────

export interface QaResult {
  passed: boolean;
  checks: { name: string; status: "pass" | "fail"; detail?: string }[];
}

interface ElementBox {
  tag: string;
  x: number; y: number; w: number; h: number;
  text?: string;
}

/**
 * Inspect the rendered SVG DOM and run structural checks.
 * Called after Plot.plot() returns the SVG node and it's been attached.
 */
export function runQa(svg: SVGSVGElement): QaResult {
  const checks: QaResult["checks"] = [];

  // 1. NaN detection — scan all text nodes for "NaN" or "undefined"
  const textEls = Array.from(svg.querySelectorAll("text"));
  const nanTexts = textEls.filter(el => {
    const t = el.textContent ?? "";
    return /\bNaN\b/i.test(t) || /\bundefined\b/i.test(t);
  });
  checks.push({
    name: "no-nan-text",
    status: nanTexts.length === 0 ? "pass" : "fail",
    detail: nanTexts.length ? `${nanTexts.length} text elements contain NaN/undefined` : undefined,
  });

  // 2. BBox overlap detection for text elements (labels colliding).
  // IMPORTANT: use getBoundingClientRect, NOT getBBox — getBBox returns
  // LOCAL coordinates per group, so text in different Plot <g> groups
  // (axis labels vs value labels vs tick labels) report boxes in
  // different spaces and everything falsely overlaps. getBoundingClientRect
  // returns viewport-space boxes including all SVG transforms.
  const textBoxes: ElementBox[] = textEls
    .filter(el => el.textContent?.trim())
    .map(el => {
      const bb = el.getBoundingClientRect();
      return { tag: "text", x: bb.x, y: bb.y, w: bb.width, h: bb.height, text: el.textContent ?? "" };
    })
    .filter(box => box.w > 1 && box.h > 1); // drop zero-size (unlaid-out) text
  let overlapCount = 0;
  for (let i = 0; i < textBoxes.length; i++) {
    for (let j = i + 1; j < textBoxes.length; j++) {
      if (boxesOverlap(textBoxes[i]!, textBoxes[j]!)) {
        // Exclude axis tick pairs that are supposed to be adjacent
        const bothAreTicks = textBoxes[i]!.h < 18 && textBoxes[j]!.h < 18 &&
          Math.abs(textBoxes[i]!.y - textBoxes[j]!.y) < 3;
        if (!bothAreTicks) overlapCount++;
      }
    }
  }
  checks.push({
    name: "no-label-overlap",
    status: overlapCount === 0 ? "pass" : "fail",
    detail: overlapCount ? `${overlapCount} overlapping text pairs detected` : undefined,
  });

  // 3. SVG has content (not just axis frame)
  const dataMarks = svg.querySelectorAll("path, rect, circle, line, polygon, ellipse, image, use");
  checks.push({
    name: "has-data-marks",
    status: dataMarks.length > 2 ? "pass" : "fail",
    detail: dataMarks.length <= 2 ? `Only ${dataMarks.length} marks` : undefined,
  });

  // 4. No full-frame rectangles (the choropleth winding bug)
  const rects = Array.from(svg.querySelectorAll("rect"));
  const svgWidth = svg.viewBox?.baseVal?.width ?? svg.clientWidth ?? 0;
  const svgHeight = svg.viewBox?.baseVal?.height ?? svg.clientHeight ?? 0;
  const fullFrameRects = rects.filter(r => {
    const w = parseFloat(r.getAttribute("width") ?? "0");
    const h = parseFloat(r.getAttribute("height") ?? "0");
    return w > svgWidth * 0.8 && h > svgHeight * 0.8;
  });
  checks.push({
    name: "no-full-frame-rect",
    status: fullFrameRects.length === 0 ? "pass" : "fail",
    detail: fullFrameRects.length ? `${fullFrameRects.length} full-frame rects (winding bug?)` : undefined,
  });

  // 5. Paths should have real extent (catch degenerate zero-area paths).
  // Only flag SHORT FILL paths — tick marks and connector lines are
  // legitimately short stroke paths with zero fill.
  const paths = Array.from(svg.querySelectorAll("path"));
  const tinyPaths = paths.filter(p => {
    const d = p.getAttribute("d") ?? "";
    const isFill = (p.getAttribute("fill") ?? "") !== "none" && p.getAttribute("fill") !== null;
    return isFill && d.length > 0 && d.length < 20;
  });
  checks.push({
    name: "no-degenerate-paths",
    status: tinyPaths.length === 0 ? "pass" : "fail",
    detail: tinyPaths.length ? `${tinyPaths.length} suspiciously short paths` : undefined,
  });

  const passed = checks.every(c => c.status === "pass");
  return { passed, checks };
}

function boxesOverlap(a: ElementBox, b: ElementBox): boolean {
  return !(a.x + a.w < b.x || b.x + b.w < a.x || a.y + a.h < b.y || b.y + b.h < a.y);
}
