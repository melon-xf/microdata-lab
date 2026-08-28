import * as Plot from "@observablehq/plot";
import { runQa } from "./qa";
import { getTheme, computeDimensions } from "./tokens";

interface ChartConfig {
  chart_type: "bar" | "line" | "area" | "dot" | "dumbbell" | "ratio_ladder" | "choropleth" | "step" | "slope" | "arrow" | "lollipop" | "strip" | "facet";
  orientation?: "horizontal" | "vertical";
  theme?: "default" | "editorial" | "bauhaus" | "swiss";
  eyebrow?: string;
  show_value_labels?: boolean;
  color_map?: Record<string, string>;
  reference?: number;
  region_key?: string;
  region_format?: "name" | "stusps" | "statfp";
  title: string;
  subtitle: string;
  source: string;
  note?: string;
  x: string;
  y: string;
  series?: string;
  ci_low?: string;
  ci_high?: string;
  value_format?: "number" | "percent" | "currency" | "compact_currency";
  color?: string;
  x_label?: string;
  y_label?: string;
  x_ticks?: number[];
  y_ticks?: number[];
  y_min?: number;
  y_max?: number;
  height?: number;
  series_order?: string[];
  line_style?: Record<string, "solid" | "dashed" | "dotted">;
  vline?: { x: number; label?: string; label_y?: number; hjust?: number; linetype?: "solid" | "dashed" | "dotted"; color?: string }[];
  facet?: string;
  annotations?: { x: string | number; y: number; text: string; dx?: number; dy?: number; fill?: string; fontSize?: number; fontWeight?: number }[];
}

declare const __CHART_CONFIG__: ChartConfig;
declare const __CHART_DATA__: Record<string, string>[];

const config = __CHART_CONFIG__;
const raw = __CHART_DATA__;
const theme = getTheme(config.theme);
const isSwiss = config.theme === "swiss";
const ink = theme.ink;
const muted = theme.muted;
const hairline = theme.hairline;
const accent = config.color ?? theme.accent;
const accentFill = theme.accentFill;
const contrast = theme.contrast;
const contrastFill = theme.contrastFill;
const palette = theme.categoryPalette;

const slotByLabel: Record<string, number> = {
  "Government programs": 0,
  "Compulsory private": 1,
  "Voluntary private": 2,
  "Out-of-pocket": 3,
  "United States": 0,
  "United States + Health Insurance": 0,
  Denmark: 1,
  Finland: 2,
  Norway: 3,
  Sweden: 4,
};
const colorForSeries = (label: string, nSeries: number): string =>
  palette[slotByLabel[label] ?? Math.min(nSeries - 1, 4)] ?? contrast;

function seriesColors(s1: string, s2: string): [string, string] {
  const fillMap: Record<string, string> = config.color_map ?? {};
  return [
    fillMap[s1] ?? (isSwiss ? accent : accent),
    fillMap[s2] ?? (isSwiss ? contrast : ink),
  ];
}

if (Boolean(config.ci_low) !== Boolean(config.ci_high)) {
  throw new Error("ci_low and ci_high must be configured together");
}
const data: Record<string, string | number>[] = raw.map((row) => {
  const normalized: Record<string, string | number> = {
    ...row,
    [config.y]: Number(row[config.y]),
  };
  const numericX = ["line", "area"].includes(config.chart_type);
  if (numericX) {
    normalized[config.x] = Number(row[config.x]);
  }
  if (config.ci_low && config.ci_high) {
    normalized[config.ci_low] = Number(row[config.ci_low]);
    normalized[config.ci_high] = Number(row[config.ci_high]);
  }
  return normalized;
});

const formatter = new Intl.NumberFormat("en-US", formatOptions(config.value_format));
// Custom format that shows "0" instead of "-0" for near-zero values.
// Post-process the formatted string rather than thresholding the raw
// value: a raw threshold (e.g. <0.05) swallows real small values like
// a 4.99% share formatted to one decimal.
function fmt(v: number): string {
  const s = formatter.format(v);
  // Replace negative-zero renders with plain zero, preserving the format's
  // suffix ("0%" for percent, "0" for number).
  if (s === "-0" || s === "-0.0" || s === "-0.00") return s.replace("-", "");
  if (s === "-0%") return "0%";
  return s;
}
function formatOptions(kind: ChartConfig["value_format"]): Intl.NumberFormatOptions {
  if (kind === "percent") return { style: "percent", maximumFractionDigits: 1 };
  if (kind === "currency") return { style: "currency", currency: "USD", maximumFractionDigits: 0 };
  if (kind === "compact_currency") {
    return { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 };
  }
  return { maximumFractionDigits: 1 };
}

function tickValues(ticks?: number[]): number[] | undefined {
  return ticks;
}

// ── Categorical x-axis crowding guard ─────────────────────────────────
// What Plot already does: nothing — a band axis renders EVERY tick label
// centered on its band and never rotates, wraps, or thins them, so crowded
// categorical labels overlap silently (Plot exposes the tickRotate option
// but leaves the decision to the caller). The R renderer's protection for
// the same case is a 30° rotation (render_static.R step branch:
// axis.text.x = element_text(angle = 30, hjust = 1)). Mirror that here,
// gated on MEASURED crowding: canvas-measure the labels (at the axis font
// size/style Plot actually renders — common.style sets fontSize/baseFontSize)
// and rotate only when the label pitch cannot fit the longest label side by
// side. NOTE: a -30° rotation shrinks each label's HORIZONTAL footprint to
// |width·cos30°| ≈ 0.87w but its bounding box still overlaps neighbors; the
// guard therefore triggers on the horizontal extent that actually collides.
let measureCtx: CanvasRenderingContext2D | null = null;
function measureTextWidth(text: string): number {
  if (!measureCtx) {
    measureCtx = document.createElement("canvas").getContext("2d");
    if (measureCtx) {
      // Match Plot's rendered tick style: common.style sets the SVG font to
      // theme.fontStack at theme.baseFontSize px.
      measureCtx.font = `${theme.baseFontSize}px ${theme.fontStack}`;
    }
  }
  // Fallback estimate when canvas is unavailable (SSR/tests).
  return measureCtx ? measureCtx.measureText(text).width : text.length * theme.baseFontSize * 0.55;
}
function crowdedXLabels(width: number, labels: string[], mLeft: number, mRight: number): boolean {
  if (labels.length < 2) return false;
  const available = width - mLeft - mRight;
  if (available <= 40) return false;
  // Horizontal footprint of a -30°-rotated label is width*cos(30°) ≈ 0.87w;
  // labels collide when consecutive footprints would touch end-to-end with
  // no breathing room. Use the LONGEST label (worst case) as the criterion —
  // mirroring ggplot behavior where rotation happens for all ticks or none.
  let longest = 0;
  for (const label of labels) longest = Math.max(longest, measureTextWidth(label));
  const rotatedFootprint = longest * Math.cos(Math.PI / 6);
  const pitch = available / labels.length;
  return rotatedFootprint > pitch * 0.98;
}

function chartForWidth(width: number): Node {
  const responsiveHorizontal = config.chart_type === "bar" && width < 560;
  const horizontal = config.orientation === "horizontal" || responsiveHorizontal;
  // Facet charts need their configured height honored (many rows); the
  // ratio-based default squashes labels. Other charts use the responsive ratio.
  const dims =
    config.chart_type === "facet" && config.height
      ? { width, height: Math.max(430, Math.min(config.height, 2200)) }
      : computeDimensions(width, config.chart_type);
  const hasValueLabels = config.show_value_labels !== false &&
    ["bar", "dumbbell", "ratio_ladder", "dot"].includes(config.chart_type);
  const isDot = config.chart_type === "dot";
  const dotLeftInset = isDot ? 4 : 0;
  const HORIZ_BY_CONSTRUCTION = ["dumbbell", "ratio_ladder", "arrow", "lollipop", "strip", "dot"];
  const needsCatMargin = horizontal || HORIZ_BY_CONSTRUCTION.includes(config.chart_type);
  let mL = needsCatMargin ? 120 : 66;
  if (needsCatMargin && config.x) {
    // For horizontal-by-construction charts (dot, lollipop, strip,
    // ratio_ladder, arrow, dumbbell), the category labels are on the
    // y-axis band, not the x-axis. Use the series column if present,
    // otherwise the x column.
    const labelCol = HORIZ_BY_CONSTRUCTION.includes(config.chart_type)
      ? (config.series ?? config.x)
      : config.x;
    const longest = Math.max(...data.map((row) => String(row[labelCol]).length), 0);
    mL = Math.max(mL, Math.min(longest * 7.5 + 24, 300));
  }
  let axisMax: number | undefined;
  let axisMin: number | undefined;
  if (config.y && !["choropleth"].includes(config.chart_type)) {
    const vals = data.map((row) => Number(row[config.y])).filter((v) => Number.isFinite(v));
    // CI error bars are banned (user directive 2026-08): the domain fits the
    // data, not interval extents.
    const ref = config.reference ?? 0;
    const m = Math.max(...vals, ref, 0);
    const lo = Math.min(...vals, ref, 0);
    axisMax = m > 0 ? m * 1.08 : undefined;
    axisMin = lo < 0 ? lo * 1.08 : 0;
  }
  const mR = hasValueLabels ? 60 : 28;
  const catCount = new Set(data.map((row) => String(row[config.x]))).size;
  let chartHeight = responsiveHorizontal ? 640 : dims.height;
  if (needsCatMargin && catCount > 12) {
    chartHeight = Math.max(chartHeight, catCount * 24 + 140);
  }
  const common = {
    width,
    height: chartHeight,
    marginTop: config.y_label ? 48 : theme.margin.top,
    marginRight: needsCatMargin ? mR : 28,
    marginBottom: theme.margin.bottom,
    marginLeft: needsCatMargin ? mL + dotLeftInset : theme.margin.left,
    style: {
      background: "transparent",
      color: ink,
      fontFamily: theme.fontStack,
      fontSize: `${theme.baseFontSize}px`,
    },
    // Value-axis label goes on the axis that carries the metric: x for
    // horizontal (value runs left-right), y for vertical (value runs
    // bottom-top). The category axis stays unlabeled — categories are
    // self-evident and a rotated value label on the category axis was the
    // "Share of GDP on the left" confusion in QA.
    x: { label: horizontal ? config.x_label ?? null : config.y_label ?? null, grid: horizontal, tickSize: 0, gridColor: hairline },
    y: { label: horizontal ? null : config.x_label ?? null, grid: !horizontal, tickSize: 0, gridColor: hairline },
  };

  // Shared annotation marks, scoped inside chartForWidth so we can consult
  // the chart orientation and a data-driven value-domain heuristic. Numeric
  // annotations on the value axis (x for horizontal charts) get a text anchor
  // that points inward, preventing long callouts from overflowing the plot
  // frame at the 480px legibility floor (2b-rung-deltas regression).
  const valueDomain: [number, number] | undefined = (() => {
    if (!config.y) return undefined;
    const vals = data.map((row) => Number(row[config.y])).filter((v) => Number.isFinite(v));
    if (vals.length === 0) return undefined;
    return [Math.min(...vals), Math.max(...vals)];
  })();
  const horizontalValueAxis = horizontal || HORIZ_BY_CONSTRUCTION.includes(config.chart_type);
  function annotationMarks() {
    if (!config.annotations) return [];
    return config.annotations.map((a) => {
      let dx = a.dx ?? 0;
      let textAnchor: "start" | "middle" | "end" | undefined = "middle";
      if (horizontalValueAxis && valueDomain && typeof a.x === "number") {
        const [lo, hi] = valueDomain;
        const range = hi - lo;
        if (range > 0) {
          const ratio = (a.x - lo) / range;
          // In the right 20% of the value axis, anchor the callout to the left
          // of the data point so it stays inside the frame.
          if (ratio > 0.8) {
            textAnchor = "end";
            dx -= 8;
          }
          // In the left 20%, anchor to the right so it clears the left edge.
          else if (ratio < 0.2) {
            textAnchor = "start";
            dx += 8;
          }
        }
      }
      return Plot.text([a], {
        // Function channels: Plot treats string values as column names, which
        // silently drops annotations whose x/y are band-name strings. Functions
        // always return literal values (numeric or band-name) instead.
        x: () => a.x,
        y: () => a.y,
        text: "text",
        dx,
        dy: a.dy ?? -12,
        fill: a.fill ?? ink,
        fontSize: a.fontSize ?? theme.annotationSize,
        fontWeight: a.fontWeight ?? theme.annotationWeight,
        textAnchor,
      });
    });
  }

  // ── Horizontal grouped bars ────────────────────────────────────────
  if (config.chart_type === "bar" && horizontal) {
    const showLabels = config.show_value_labels !== false;
    const fillKey = (row: Record<string, string | number>) =>
      String(row[config.series ?? config.x]);
    const fillMap =
      config.color_map ??
      (config.theme === "swiss"
        ? { "United States": accent }
        : {});
    const subjectFill = (row: Record<string, string | number>) =>
      fillKey(row) in fillMap
        ? fillMap[fillKey(row)]
        : config.color ?? (config.theme === "swiss"
          ? contrast
          : accent);
    const bands = config.series
      ? [...new Set(data.map((row) => String(row[config.x])))]
      : [];
    const groups = config.series
      ? [...new Set(data.map((row) => String(row[config.series!])))]
      : [];
    const n = groups.length;
    const edge = 0.1;
    const gap = 0.1;
    const slot = n > 0 ? (1 - edge - gap * (n - 1)) / n : 1;
    const legendOrder = config.color_map ? Object.keys(config.color_map) : groups;
    const groupPos = (group: string) =>
      legendOrder.indexOf(group) >= 0 ? n - 1 - legendOrder.indexOf(group) : groups.indexOf(group);
    const pos = (band: string, group: string) =>
      bands.indexOf(band) + edge / 2 + groupPos(group) * (slot + gap);
    const bandDomain = config.series ? bands : data.map((row) => String(row[config.x]));
    const yScale = config.series
      ? {
          type: "linear" as const,
          domain: [0, bands.length],
          ticks: bands.map((_, i) => i + 0.5),
          tickFormat: (v: number) => bands[Math.round(v - 0.5)] ?? "",
          label: common.y.label,
          grid: false,
          tickSize: 0,
        }
      : { ...common.y, type: "band" as const, domain: bandDomain, padding: 0.35 };
    return Plot.plot({
      ...common,
      x: {
        ...common.x,
        tickFormat: (value: number) => formatter.format(value),
        ...(config.y_min != null || config.y_max != null
          ? { domain: [config.y_min ?? axisMin ?? 0, config.y_max ?? axisMax ?? 0] }
          : axisMax != null
            ? { domain: [axisMin ?? 0, axisMax] }
            : {}),
      },
      y: yScale,
      color:
        config.series && (config.color_map || (config.theme === "swiss" && data.some((r) => String(r[config.series!]) === "United States")))
          ? {
              type: "ordinal",
              domain: [...new Set(data.map((row) => fillKey(row)))],
              range: [...new Set(data.map((row) => subjectFill(row)))],
              legend: true,
            }
          : undefined,
      marks: [
        config.series
          ? Plot.rectX(data, {
              y1: (row: Record<string, string | number>) => pos(String(row[config.x]), String(row[config.series!])),
              y2: (row: Record<string, string | number>) => pos(String(row[config.x]), String(row[config.series!])) + slot,
              x1: 0,
              x2: config.y,
              fill:
                config.color_map ||
                (config.theme === "swiss" && data.some((r) => String(r[config.series!]) === "United States"))
                  ? fillKey
                  : subjectFill,
              rx: 2,
              tip: true,
            })
          : Plot.barX(data, { x: config.y, y: config.x, fill: subjectFill, rx: 2, tip: true }),
        ...(showLabels
          ? [
              // Positive bars: label to the right of the bar end. Anchoring
              // past the bar end created long leader lines on dense grouped charts
              // (6a QA) — bar-end is standard.
              Plot.text(data.filter((row) => Number(row[config.y]) >= 0), {
                x: config.y,
                y: config.series
                  ? (row: Record<string, string | number>) => pos(String(row[config.x]), String(row[config.series!])) + slot / 2
                  : config.x,
                text: (row: Record<string, string | number>) => fmt(Number(row[config.y])),
                dx: 8,
                textAnchor: "start",
                fontWeight: theme.valueLabelWeight,
                fill: ink,
              }),
              // Negative bars: label to the left of the bar end so it clears
              // the bar instead of sitting inside it.
              Plot.text(data.filter((row) => Number(row[config.y]) < 0), {
                x: config.y,
                y: config.series
                  ? (row: Record<string, string | number>) => pos(String(row[config.x]), String(row[config.series!])) + slot / 2
                  : config.x,
                text: (row: Record<string, string | number>) => fmt(Number(row[config.y])),
                dx: -8,
                textAnchor: "end",
                fontWeight: theme.valueLabelWeight,
                fill: ink,
              }),
            ]
          : []),
        Plot.ruleX([0], { stroke: muted }),
        ...annotationMarks(),
      ],
    });
  }

  // ── Vertical bars ───────────────────────────────────────────────────
  if (config.chart_type === "bar") {
    const showLabels = config.show_value_labels !== false;
    const fillKey = (row: Record<string, string | number>) =>
      String(row[config.series ?? config.x]);
    const fillMap =
      config.color_map ??
      (config.theme === "swiss"
        ? { "United States": accent }
        : {});
    const subjectFill = (row: Record<string, string | number>) =>
      fillKey(row) in fillMap
        ? fillMap[fillKey(row)]
        : config.color ?? (config.theme === "swiss"
          ? contrast
          : accent);
    const bands = config.series
      ? [...new Set(data.map((row) => String(row[config.x])))]
      : [];
    const groups = config.series
      ? [...new Set(data.map((row) => String(row[config.series!])))]
      : [];
    const n = groups.length;
    const edge = 0.1;
    const gap = 0.1;
    const slot = n > 0 ? (1 - edge - gap * (n - 1)) / n : 1;
    const legendOrder = config.color_map ? Object.keys(config.color_map) : groups;
    const groupPos = (group: string) =>
      legendOrder.indexOf(group) >= 0 ? n - 1 - legendOrder.indexOf(group) : groups.indexOf(group);
    const pos = (band: string, group: string) =>
      bands.indexOf(band) + edge / 2 + groupPos(group) * (slot + gap);
    return Plot.plot({
      ...common,
      // Crowding guard: Plot band axes never rotate labels; the R renderer
      // rotates crowded categorical ticks 30° (render_static.R). Mirror that,
      // gated on measured width so sparse charts keep flat centered labels.
      x: config.series
        ? {
            type: "linear",
            domain: [0, bands.length],
            ticks: bands.map((_, i) => i + 0.5),
            tickFormat: (v: number) => bands[Math.round(v - 0.5)] ?? "",
            label: common.x.label,
            grid: false,
          }
        : {
            ...common.x,
            type: "band",
            domain: data.map((row) => String(row[config.x])),
            ...(crowdedXLabels(width, [...new Set(data.map((row) => String(row[config.x])))], common.marginLeft, common.marginRight)
              ? { tickRotate: -30 }
              : {}),
          },
      y: {
        ...common.y,
        tickFormat: (value: number) => formatter.format(value),
        ...(config.y_min != null || config.y_max != null
          ? { domain: [config.y_min ?? axisMin ?? 0, config.y_max ?? axisMax ?? 0] }
          : axisMax != null
            ? { domain: [axisMin ?? 0, axisMax] }
            : {}),
      },
      color:
        config.series && (config.color_map || (config.theme === "swiss" && data.some((r) => String(r[config.series!]) === "United States")))
          ? {
              type: "ordinal",
              domain: [...new Set(data.map((row) => fillKey(row)))],
              range: [...new Set(data.map((row) => subjectFill(row)))],
              legend: true,
            }
          : undefined,
      marks: [
        config.series
          ? Plot.rectY(data, {
              x1: (row: Record<string, string | number>) => pos(String(row[config.x]), String(row[config.series!])),
              x2: (row: Record<string, string | number>) => pos(String(row[config.x]), String(row[config.series!])) + slot,
              y1: 0,
              y2: config.y,
              fill:
                config.color_map ||
                (config.theme === "swiss" && data.some((r) => String(r[config.series!]) === "United States"))
                  ? fillKey
                  : subjectFill,
              rx: 2,
              tip: true,
            })
          : Plot.barY(data, {
              x: config.x,
              y: config.y,
              fill: subjectFill,
              rx: 2,
              tip: true,
            }),
        ...(showLabels
          ? [Plot.text(data, {
              x: config.series
                ? (row: Record<string, string | number>) => pos(String(row[config.x]), String(row[config.series!])) + slot / 2
                : config.x,
              y: config.y,
              text: (row) => fmt(Number(row[config.y])),
              dy: -10,
              fontWeight: theme.valueLabelWeight,
              fill: ink,
            })]
          : []),
        ...(config.reference != null
          ? [
              Plot.ruleX([config.reference], { stroke: ink, strokeDasharray: "6,4", strokeWidth: theme.strokeWidthThin }),
              Plot.text([{ x: config.reference, label: "parity" }], {
                x: "x",
                text: "label",
                dy: 8,
                dx: 4,
                textAnchor: "start",
                fill: muted,
                fontSize: theme.annotationSize,
                fontStyle: "italic",
              }),
            ]
          : []),
        Plot.ruleY([0], { stroke: muted }),
        ...annotationMarks(),
      ],
    });
  }

  // ── line: single or multi-series time/ordered trend ─────────────────
  if (config.chart_type === "line" && config.series) {
    const groups = [...new Set(data.map((row) => String(row[config.series!])))];
    const lineColors = groups.map(
      (group) => config.color_map?.[group] ?? colorForSeries(group, groups.length),
    );
    const solidData = data.filter((row) => {
      const ls = config.line_style?.[String(row[config.series!])];
      return !ls || ls === "solid";
    });
    const dashedData = data.filter((row) => {
      const ls = config.line_style?.[String(row[config.series!])];
      return ls === "dashed";
    });
    return Plot.plot({
      ...common,
      x: { ...common.x, label: config.x_label ?? null },
      y: {
        ...common.y,
        label: config.y_label ?? null,
        tickFormat: (value: number) => formatter.format(value),
      },
      marginBottom: config.x_label ? 60 : common.marginBottom,
      color: { domain: groups, range: lineColors, legend: true },
      marks: [
        ...(solidData.length
          ? [Plot.lineY(solidData, { x: config.x, y: config.y, stroke: config.series, strokeWidth: theme.strokeWidth, tip: true })]
          : []),
        ...(dashedData.length
          ? [Plot.lineY(dashedData, {
              x: config.x,
              y: config.y,
              stroke: config.series,
              strokeWidth: theme.strokeWidth,
              strokeDasharray: "5,4",
              tip: true,
            })]
          : []),
        Plot.dot(data, { x: config.x, y: config.y, fill: config.series, r: theme.dotRadius, stroke: "#FFFFFF", strokeWidth: theme.strokeWidthThin, tip: true }),
        ...(config.vline
          ? config.vline.flatMap((line) => [
              Plot.ruleX([line.x], { stroke: line.color ?? muted, strokeDasharray: line.linetype === "dashed" ? "6,4" : undefined }),
              ...(line.label
                ? [Plot.text([{ x: line.x, label: line.label }], {
                    x: "x",
                    text: "label",
                    dy: line.label_y ?? -8,
                    dx: line.hjust === 1 ? -4 : 4,
                    textAnchor: line.hjust === 1 ? "end" : "start",
                    fill: line.color ?? muted,
                    fontSize: theme.valueLabelSize,
                    fontStyle: "italic",
                  })]
                : []),
            ])
          : []),
        ...annotationMarks(),
      ],
    });
  }

  // ── line: single series ────────────────────────────────────────────
  if (config.chart_type === "line") {
    return Plot.plot({
      ...common,
      marginBottom: config.x_label ? 60 : common.marginBottom,
      x: { ...common.x, label: config.x_label ?? null },
      y: {
        ...common.y,
        label: config.y_label ?? null,
        tickFormat: (value: number) => formatter.format(value),
      },
      marks: [
        Plot.lineY(data, { x: config.x, y: config.y, stroke: accent, strokeWidth: theme.strokeWidth, tip: true }),
        Plot.dot(data, { x: config.x, y: config.y, fill: accent, r: theme.dotRadius, tip: true }),
        Plot.ruleY([0], { stroke: muted }),
        ...(config.vline
          ? config.vline.flatMap((line) => [
              Plot.ruleX([line.x], { stroke: line.color ?? muted, strokeDasharray: line.linetype === "dashed" ? "6,4" : undefined }),
              ...(line.label
                ? [Plot.text([{ x: line.x, label: line.label }], {
                    x: "x",
                    text: "label",
                    dy: line.label_y ?? -8,
                    dx: line.hjust === 1 ? -4 : 4,
                    textAnchor: line.hjust === 1 ? "end" : "start",
                    fill: line.color ?? muted,
                    fontSize: theme.valueLabelSize,
                    fontStyle: "italic",
                  })]
                : []),
            ])
          : []),
        ...annotationMarks(),
      ],
    });
  }

  // ── slope: two-series lines with direct end-labels ─────────────────
  if (config.chart_type === "slope") {
    const seriesKey = config.series!;
    const seriesDomain = [...new Set(data.map((row) => String(row[seriesKey])))];
    const [s1, s2] = [seriesDomain[0]!, seriesDomain[1]!];
    const bands = [...new Set(data.map((row) => String(row[config.x])))];
    const wide = bands.map((band) => {
      const row1 = data.find((r) => String(r[config.x]) === band && String(r[seriesKey]) === s1);
      const row2 = data.find((r) => String(r[config.x]) === band && String(r[seriesKey]) === s2);
      return {
        band,
        v1: row1 ? Number(row1[config.y]) : NaN,
        v2: row2 ? Number(row2[config.y]) : NaN,
      };
    });
    const [c1, c2] = seriesColors(s1, s2);
    // Per-band label side: the series that is HIGHER at a band gets its
    // label ABOVE the line; the LOWER series gets its label BELOW.
    // Plot 0.6: dx/dy are static per mark, so each side is a separate
    // filtered Plot.text.
    const sideByBand = new Map(
      bands.map((band) => {
        const row = wide.find((r) => r.band === band)!;
        return [band, row.v1 >= row.v2 ? "above" : "below"];
      })
    );
    const isAbove = (band: string) => sideByBand.get(band) === "above";
    return Plot.plot({
      ...common,
      x: {
        ...common.x,
        type: "band",
        domain: bands,
        // Crowding guard: mirror the R renderer's 30° rotation for crowded
        // categorical ticks (gated on measured width, not applied blindly).
        ...(crowdedXLabels(width, bands, common.marginLeft, common.marginRight) ? { tickRotate: -30 } : {}),
      },
      y: { ...common.y, tickFormat: (value: number) => formatter.format(value) },
      color: {
        type: "ordinal",
        domain: seriesDomain,
        range: [c1, c2],
        legend: true,
      },
      marks: [
        Plot.lineY(wide, { x: "band", y: "v1", stroke: c1, strokeWidth: theme.strokeWidth, tip: true }),
        Plot.lineY(wide, { x: "band", y: "v2", stroke: c2, strokeWidth: theme.strokeWidth, tip: true }),
        Plot.dot(wide, { x: "band", y: "v1", fill: c1, r: theme.dotRadius, tip: true }),
        Plot.dot(wide, { x: "band", y: "v2", fill: c2, r: theme.dotRadius, tip: true }),
        // Labels: above for higher series, below for lower
        Plot.text(
          wide.filter((r) => isAbove(r.band)),
          { x: "band", y: "v1", text: (r: { v1: number }) => formatter.format(r.v1), dy: -9, textAnchor: "end", fill: c1, fontWeight: theme.valueLabelWeight, fontSize: theme.valueLabelSize }
        ),
        Plot.text(
          wide.filter((r) => !isAbove(r.band)),
          { x: "band", y: "v1", text: (r: { v1: number }) => formatter.format(r.v1), dy: 12, textAnchor: "end", fill: c1, fontWeight: theme.valueLabelWeight, fontSize: theme.valueLabelSize }
        ),
        Plot.text(
          wide.filter((r) => !isAbove(r.band)),
          { x: "band", y: "v2", text: (r: { v2: number }) => formatter.format(r.v2), dy: -9, textAnchor: "start", fill: c2, fontWeight: theme.valueLabelWeight, fontSize: theme.valueLabelSize }
        ),
        Plot.text(
          wide.filter((r) => isAbove(r.band)),
          { x: "band", y: "v2", text: (r: { v2: number }) => formatter.format(r.v2), dy: 12, textAnchor: "start", fill: c2, fontWeight: theme.valueLabelWeight, fontSize: theme.valueLabelSize }
        ),
        // Gap annotation at the widest band
        ...(() => {
          const byBand = new Map(
            wide.map((r) => [r.band, { gap: Math.abs(r.v2 - r.v1), yA: 0, yB: 0 }])
          );
          const widest = [...byBand.entries()].reduce((a, b) => (a[1].gap > b[1].gap ? a : b));
          const gapMid = (byBand.get(widest[0])!.yA + byBand.get(widest[0])!.yB) / 2;
          return [
            Plot.text([{ b: widest[0], mid: gapMid, gap: widest[1].gap }], {
              x: "b",
              y: "mid",
              text: (row) => `${formatter.format(row.gap)} gap`,
              dy: -22,
              textAnchor: "middle",
              fill: ink,
              fontWeight: theme.valueLabelWeight,
              fontSize: theme.valueLabelSize,
            }),
          ];
        })(),
        Plot.ruleY([0], { stroke: muted }),
      ...annotationMarks(),
      ],
    });
  }

  // ── step: monotone descent as a step area ───────────────────────────
  if (config.chart_type === "step") {
    const bands = [...new Set(data.map((row) => String(row[config.x])))];
    const stepped = data.map((row) => {
      const band = String(row[config.x]);
      return { ...row, __pos: bands.indexOf(band) };
    });
    const last = stepped[stepped.length - 1]!;
    stepped.push({ ...last, __pos: bands.length });
    return Plot.plot({
      ...common,
      x: {
        ...common.x,
        ticks: bands.map((_, i) => i),
        tickFormat: (v: number) => bands[v] ?? "",
        type: "linear",
        label: null,
        // Crowding guard: mirror the R step chart's 30° rotation for crowded
        // band labels (gated on measured width; the R branch sets angle=30).
        ...(crowdedXLabels(width, bands, common.marginLeft, common.marginRight) ? { tickRotate: -30 } : {}),
      },
      y: {
        ...common.y,
        tickFormat: (value: number) => (value === 0 ? "" : formatter.format(value)),
        ...(config.y_min != null || config.y_max != null
          ? { domain: [config.y_min ?? undefined, config.y_max ?? undefined] }
          : {}),
      },
      marks: [
        Plot.areaY(stepped, {
          x: "__pos",
          y: config.y,
          fill: accentFill,
          curve: "step-after",
          tip: true,
        }),
        Plot.lineY(stepped, {
          x: "__pos",
          y: config.y,
          stroke: accent,
          strokeWidth: theme.strokeWidth,
          curve: "step-after",
          tip: true,
        }),
        Plot.ruleY([0], { stroke: muted }),
      ...annotationMarks(),
      ],
    });
  }

  // ── dumbbell: per-category pair of points + connector ───────────────
  if (config.chart_type === "dumbbell") {
    const seriesKey = config.series!;
    const seriesDomain = [...new Set(data.map((row) => String(row[seriesKey])))];
    const [s1, s2] = [seriesDomain[0]!, seriesDomain[1]!];
    const bands = [...new Set(data.map((row) => String(row[config.x])))];
    const wide = bands.map((band) => {
      const row1 = data.find((r) => String(r[config.x]) === band && String(r[seriesKey]) === s1);
      const row2 = data.find((r) => String(r[config.x]) === band && String(r[seriesKey]) === s2);
      return {
        band,
        v1: row1 ? Number(row1[config.y]) : NaN,
        v2: row2 ? Number(row2[config.y]) : NaN,
      };
    });
    const [c1, c2] = seriesColors(s1, s2);
    const dVals = wide.flatMap((r) => [r.v1, r.v2]).filter((v) => Number.isFinite(v));
    const dMin = Math.min(...dVals);
    const dMax = Math.max(...dVals);
    const dPad = (dMax - dMin) * 0.12 || 2;
    return Plot.plot({
      ...common,
      // Full domain from 0 (share scale): a tight auto-range like [36, 49]
      // clips the lower dot off-canvas and hides the comparison.
      x: { ...common.x, domain: [Math.min(0, dMin - dPad), dMax + dPad], tickFormat: (value: number) => formatter.format(value) },
      y: { type: "band", domain: bands, label: null, grid: false },
      color: {
        type: "ordinal",
        domain: seriesDomain,
        range: [c1, c2],
        legend: true,
      },
      marks: [
        Plot.ruleY(wide, {
          y: "band",
          x1: "v1",
          x2: "v2",
          stroke: muted,
          strokeWidth: theme.strokeWidthThin,
        }),
        Plot.dot(wide, { y: "band", x: "v1", fill: c1, r: theme.dotRadiusLarge, tip: true }),
        Plot.dot(wide, { y: "band", x: "v2", fill: c2, r: theme.dotRadiusLarge, tip: true }),
        // Label each endpoint with its own value (not the gap — the gap is in
        // the title). Left dot labeled to its left, right dot to its right.
        Plot.text(wide, {
          y: "band",
          x: "v1",
          text: (row: { band: string; v1: number; v2: number }) => formatter.format(row.v1),
          dx: -10,
          textAnchor: "end",
          fontWeight: theme.valueLabelWeight,
          fill: c1,
          fontSize: theme.annotationSize,
        }),
        Plot.text(wide, {
          y: "band",
          x: "v2",
          text: (row: { band: string; v1: number; v2: number }) => formatter.format(row.v2),
          dx: 10,
          textAnchor: "start",
          fontWeight: theme.valueLabelWeight,
          fill: c2,
          fontSize: theme.annotationSize,
        }),
        Plot.ruleY([0], { stroke: muted }),
        ...annotationMarks(),
      ],
    });
  }

  // ── arrow: per-category arrow from comparison to subject ────────────
  if (config.chart_type === "arrow") {
    const seriesKey = config.series!;
    const seriesDomain = [...new Set(data.map((row) => String(row[seriesKey])))];
    const [s1, s2] = [seriesDomain[0]!, seriesDomain[1]!];
    const bands = [...new Set(data.map((row) => String(row[config.x])))];
    const wide = bands.map((band) => {
      const row1 = data.find((r) => String(r[config.x]) === band && String(r[seriesKey]) === s1);
      const row2 = data.find((r) => String(r[config.x]) === band && String(r[seriesKey]) === s2);
      return {
        band,
        v1: row1 ? Number(row1[config.y]) : NaN,
        v2: row2 ? Number(row2[config.y]) : NaN,
      };
    });
    const [c1, c2] = seriesColors(s1, s2);
    const vals = wide.flatMap((r) => [r.v1, r.v2]).filter((v) => Number.isFinite(v));
    const vMin = Math.min(...vals);
    const vMax = Math.max(...vals);
    const pad = (vMax - vMin) * 0.08 || 0.02;
    return Plot.plot({
      ...common,
      x: {
        ...common.x,
        domain: [vMin - pad, vMax + pad * 1.6],
        tickFormat: (value: number) => formatter.format(value),
        label: config.x_label ?? null,
      },
      y: { type: "band", domain: bands, label: null, grid: false },
      color: {
        type: "ordinal",
        domain: seriesDomain,
        range: [c1, c2],
        legend: true,
      },
      marks: [
        Plot.arrow(wide, {
          y: "band",
          x1: "v2",
          x2: "v1",
          stroke: muted,
          strokeWidth: theme.strokeWidthThin,
          headLength: 14,
          inset: 10,
        }),
        Plot.dot(wide, { y: "band", x: "v1", fill: c1, r: theme.dotRadiusLarge, tip: true }),
        Plot.dot(wide, { y: "band", x: "v2", fill: c2, r: theme.dotRadiusLarge, tip: true }),
        Plot.text(wide.filter((r) => r.v1 >= r.v2), {
          y: "band", x: "v1",
          text: (r: { v1: number }) => formatter.format(r.v1),
          dx: 14, textAnchor: "start", fontWeight: theme.valueLabelWeight, fill: c1, fontSize: theme.valueLabelSize,
        }),
        Plot.text(wide.filter((r) => r.v1 < r.v2), {
          y: "band", x: "v1",
          text: (r: { v1: number }) => formatter.format(r.v1),
          dx: -14, textAnchor: "end", fontWeight: theme.valueLabelWeight, fill: c1, fontSize: theme.valueLabelSize,
        }),
        Plot.text(wide.filter((r) => r.v2 > r.v1), {
          y: "band", x: "v2",
          text: (r: { v2: number }) => formatter.format(r.v2),
          dx: 14, textAnchor: "start", fontWeight: theme.axisLabelWeight, fill: muted, fontSize: theme.annotationSize,
        }),
        Plot.text(wide.filter((r) => r.v2 <= r.v1), {
          y: "band", x: "v2",
          text: (r: { v2: number }) => formatter.format(r.v2),
          dx: -14, textAnchor: "end", fontWeight: theme.axisLabelWeight, fill: muted, fontSize: theme.annotationSize,
        }),
        Plot.text(wide, {
          y: "band",
          x: (r: { v1: number; v2: number }) => (r.v1 + r.v2) / 2,
          // Gap must match what the reader computes from the DISPLAYED values:
          // round both endpoints to 1 decimal first, then diff. Raw values
          // (0.55) disagree with displayed (15.7 - 15.1 = 0.6).
          text: (r) => {
            const d1 = Math.round(r.v1 * 1000) / 10;
            const d2 = Math.round(r.v2 * 1000) / 10;
            return `${Math.abs(d1 - d2).toFixed(1)} pts`;
          },
          dy: -14,
          textAnchor: "middle",
          fontWeight: theme.valueLabelWeight,
          fill: ink,
          fontSize: theme.annotationSize,
        }),
        ...annotationMarks(),
      ],
    });
  }

  // ── lollipop: dot + stem from reference (deviation / distance) ──────
  if (config.chart_type === "lollipop") {
    const baseline = config.reference ?? 0;
    const fillFor = (row: Record<string, string | number>) => {
      const key = String(row[config.series ?? config.x]);
      // If a color_map exists but lacks this key, use the neutral contrast
      // (gray) so only mapped series carry the accent.
      return config.color_map ? (config.color_map[key] ?? contrast) : accent;
    };
    const vals = data.map((row) => Number(row[config.y])).filter((v) => Number.isFinite(v));
    const vMin = Math.min(...vals, baseline);
    const vMax = Math.max(...vals, baseline);
    const pad = Math.max((vMax - vMin) * 0.08, Math.abs(vMin) * 0.25, 0.5);
    // Consistent one-decimal labels: 57 -> "57.0", 0 -> "0.0" (matches 52.9, -1.6)
    const labelFmt = new Intl.NumberFormat("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    return Plot.plot({
      ...common,
      x: { ...common.x, domain: [vMin - pad, vMax + pad], tickFormat: (value: number) => formatter.format(value) },
      y: { type: "band", domain: data.map((row) => String(row[config.x])), label: null, grid: false },
      marks: [
        // Dashed reference line at the baseline (e.g. US at 100%) so the
        // subtitle's "dashed line = reference" promise is drawn, not implied.
        ...(baseline !== 0
          ? [Plot.ruleX([baseline], { stroke: muted, strokeDasharray: "6,4", strokeWidth: theme.strokeWidthThin })]
          : [Plot.ruleX([0], { stroke: muted })]),
        Plot.ruleY(data, {
          y: config.x,
          x1: baseline,
          x2: config.y,
          stroke: muted,
          strokeWidth: theme.strokeWidthThin,
        }),
        Plot.dot(data, {
          y: config.x,
          x: config.y,
          r: theme.dotRadiusLarge,
          fill: fillFor,
          tip: true,
        }),
        Plot.text(
          data.filter((row) => Number(row[config.y]) >= baseline),
          {
            y: config.x, x: config.y,
            text: (row: Record<string, string | number>) => labelFmt.format(Number(row[config.y])),
            dx: 13, textAnchor: "start", fontWeight: theme.valueLabelWeight, fill: ink, fontSize: theme.annotationSize + 0.5,
          },
        ),
        Plot.text(
          data.filter((row) => Number(row[config.y]) < baseline),
          {
            y: config.x, x: config.y,
            text: (row: Record<string, string | number>) => labelFmt.format(Number(row[config.y])),
            // Negative labels sit OUTSIDE the dot (away from the baseline),
            // so they never overlap the stem.
            dx: -13, textAnchor: "end", fontWeight: theme.valueLabelWeight, fill: ink, fontSize: theme.annotationSize + 0.5,
          },
        ),
        ...annotationMarks(),
      ],
    });
  }

  // ── strip: jittered dots per category, median tick ──────────────────
  if (config.chart_type === "strip") {
    // Row order matches title order: first category in data (e.g.
    // Non-expansion) renders on TOP so the leading number in the headline
    // is the first row the reader sees. Reversing the cats array keeps
    // positions, ticks, and median anchors consistent.
    const cats = [...new Set(data.map((row) => String(row[config.x])))].reverse();
    const vals = data.map((r) => Number(r[config.y])).filter((v) => Number.isFinite(v));
    const vMin = Math.min(...vals);
    const vMax = Math.max(...vals);
    const pad = (vMax - vMin) * 0.06 || 0.01;
    const pts = data.map((row) => {
      const cat = String(row[config.x]);
      const v = Number(row[config.y]);
      const catIndex = cats.indexOf(cat);
      const seed = parseInt(String(row[config.region_key ?? "stusps"] ?? "0").replace(/\D/g, "") || "0", 10);
      const jitter = ((seed % 17) - 8) * 0.08;
      const group = row[config.series ?? config.x];
      return { cat, v, gy: catIndex + 0.5 + jitter, g: group };
    });
    const medians = cats.map((cat) => {
      const catVals = pts.filter((p) => p.cat === cat).map((p) => p.v).sort((a, b) => a - b);
      const med = catVals.length % 2 === 0
        ? (catVals[catVals.length / 2 - 1]! + catVals[catVals.length / 2]!) / 2
        : catVals[Math.floor(catVals.length / 2)]!;
      return { cat, med, i: cats.indexOf(cat) + 0.5 };
    });
    const groupColors = [...new Set(pts.map((p) => p.g))];
    return Plot.plot({
      ...common,
      x: { ...common.x, domain: [vMin - pad, vMax + pad], tickFormat: (value: number) => formatter.format(value) },
      y: { type: "linear", domain: [-0.1, cats.length - 0.1], ticks: cats.map((_, i) => i + 0.5), tickFormat: (_, i) => cats[i] ?? "", label: null, grid: false },
      color: {
        type: "ordinal",
        domain: groupColors,
        range: groupColors.map((g) => config.color_map?.[g ?? ""] ?? accent),
        legend: true,
      },
      marks: [
        Plot.dot(pts, {
          x: "v",
          y: "gy",
          r: theme.dotRadiusSmall,
          fill: "g",
          fillOpacity: 0.72,
          tip: true,
        }),
        Plot.ruleX(medians, {
          x: "med",
          y1: (m: { i: number }) => m.i - 0.3,
          y2: (m: { i: number }) => m.i + 0.3,
          stroke: ink,
          strokeWidth: theme.strokeWidthThin,
        }),
        Plot.text(medians, {
          x: "med",
          y: "i",
          text: (m: { med: number }) => `median ${formatter.format(m.med)}`,
          textAnchor: "middle",
          fontSize: theme.annotationSize,
          fontWeight: theme.valueLabelWeight,
          fill: ink,
        }),
        ...annotationMarks(),
      ],
    });
  }

  // ── ratio_ladder: marker per category on a ratio scale vs reference ─
  if (config.chart_type === "ratio_ladder") {
    const reference = config.reference ?? 1.0;
    const bands = [...new Set(data.map((row) => String(row[config.x])))];
    const maxRatio = Math.max(reference, ...data.map((row) => Number(row[config.y])));
    return Plot.plot({
      ...common,
      x: { ...common.x, domain: [reference, maxRatio * 1.15], tickFormat: (value: number) => `${formatter.format(value)}×` },
      y: { type: "band", domain: bands, label: null, grid: false },
      marks: [
        Plot.ruleX([reference], { stroke: muted, strokeDasharray: "4,3" }),
        Plot.text([{ x: reference, label: "parity" }], {
          x: "x",
          text: "label",
          dy: -18,
          dx: 6,
          fill: muted,
          fontSize: theme.annotationSize,
          fontStyle: "italic",
        }),
        Plot.dot(data, {
          x: config.y,
          y: config.x,
          r: theme.dotRadiusLarge,
          fill: accent,
          tip: true,
        }),
        Plot.text(data, {
          x: config.y,
          y: config.x,
          text: (row) => `${formatter.format(Number(row[config.y]))}×`,
          dx: 16,
          textAnchor: "start",
          fontWeight: theme.valueLabelWeight,
          fill: ink,
        }),
        ...annotationMarks(),
      ],
    });
  }

  // ── facet: small-multiples of ranked bars by category (e.g. region) ─
  // Each facet is its OWN plot with a per-facet band scale. A single
  // Plot.plot with fy + shared y-scale squeezes 51 states into every frame
  // (~10px rows + empty bands). Four stacked plots keep rows legible.
  if (config.chart_type === "facet") {
    const facetKey = config.facet ?? "facet";
    const facets = [...new Set(data.map((row) => String(row[facetKey])))];
    const showLabels = config.show_value_labels !== false;
    const perFacet = facets.map((facetVal) => {
      const rows = data.filter((row) => String(row[facetKey]) === facetVal);
      const uniqueRows = new Set(rows.map((row) => String(row[config.x]))).size;
      // Size each facet by its own row count (~30px/row + axes + title).
      // The shared config height would make every facet 2200px tall.
      const facetHeight = Math.max(280, uniqueRows * 30 + 120);
      return Plot.plot({
        ...common,
        height: facetHeight,
        marginLeft: 90,
        x: {
          ...common.x,
          tickFormat: (value: number) => formatter.format(value),
          ...(axisMax != null ? { domain: [axisMin ?? 0, axisMax] } : {}),
          // Facet bars are horizontal (barX): the value axis is x, so the
          // x_label must be applied here — common.x drops it for
          // vertical-flagged configs.
          label: config.x_label ?? null,
        },
        y: {
          type: "band",
          domain: [...new Set(rows.map((row) => String(row[config.x])))],
          label: facetVal,
          grid: false,
          tickSize: 0,
        },
        color: {
          type: "ordinal",
          domain: Object.keys(config.color_map ?? {}),
          range: Object.values(config.color_map ?? {}),
          legend: facetVal === facets[0],
        },
        marks: [
          Plot.barX(rows, {
            y: config.x,
            x: config.y,
            fill: (row: Record<string, string | number>) => {
              const key = String(row[config.series ?? config.x]);
              return config.color_map?.[key] ?? accent;
            },
            sort: { y: "-x" },
            tip: true,
          }),
          ...(showLabels
            ? [Plot.text(rows, {
                y: config.x,
                x: config.y,
                text: (row: Record<string, string | number>) => formatter.format(Number(row[config.y])),
                dx: 6,
                textAnchor: "start",
                fill: ink,
                fontWeight: theme.valueLabelWeight,
                fontSize: theme.valueLabelSize,
              })]
            : []),
          ...annotationMarks(),
        ],
      });
    });
    const wrap = document.createElement("div");
    wrap.style.cssText = "display:flex;flex-direction:column;gap:8px;width:100%";
    for (const p of perFacet) wrap.appendChild(p);
    return wrap;
  }

  // ── choropleth: US state map colored by a data value ────────────────
  if (config.chart_type === "choropleth") {
    const states = (window as unknown as { __US_STATES__?: unknown }).__US_STATES__ as
      | { type: string; features: { properties: { name: string; stusps: string; statfp: string }; geometry: unknown }[] }
      | undefined;
    if (!states) {
      return document.createTextNode("Map data not loaded");
    }
    const regionOf = (feature: { properties: { name: string; stusps: string; statfp: string } }): string => {
      if (config.region_format === "stusps") return feature.properties.stusps;
      if (config.region_format === "statfp") return feature.properties.statfp;
      return feature.properties.name;
    };
    const valueByRegion = new Map<string, number>();
    for (const row of data) {
      const key = String(row[config.region_key ?? "region"]);
      valueByRegion.set(key, Number(row[config.y]));
    }
    const vals = [...valueByRegion.values()].filter((v) => Number.isFinite(v));
    const vMin = Math.min(...vals);
    const vMax = Math.max(...vals);
    // CVD-safe sequential ramp (ColorBrewer BuPu 6-step): red-only sequential
    // scales lose their signal for protan/deutan viewers (wiki 03). Light
    // blue → deep purple keeps luminance contrast for the low→high encoding.
    const buPu = ["#E0ECF4", "#BFD3E6", "#9EBCDA", "#8C96C6", "#8C6BB1", "#88419D"];
    // Legend ticks must span the TRUE data range (Plot's auto-"nice" ticks
    // like 5/10/15/20 silently drop TX's 22.2% and MA/DC/HI's 3.6-3.8%,
    // making the darkest color read as ">=20%" — a legend/data mismatch).
    const tickCount = 5;
    const step = (vMax - vMin) / (tickCount - 1);
    const legendTicks = Array.from({ length: tickCount }, (_, i) => vMin + step * i);
    return Plot.plot({
      ...common,
      projection: { type: "albers-usa" },
      color: {
        type: "sequential",
        domain: [vMin, vMax],
        range: buPu,
        legend: "ramp" as any,
        marginLeft: 18,
        marginRight: 18,
        ticks: legendTicks,
        tickFormat: (v: number) => `${(v * 100).toFixed(1)}%`,
        label: "Uninsured share →",
      } as any,
      marks: [
        Plot.geo(states, {
          fill: (d: { properties: { name: string; stusps: string; statfp: string } }) =>
            valueByRegion.get(regionOf(d)) ?? NaN,
          stroke: "#FFFFFF",
          strokeWidth: 0.5,
          tip: true,
        }),
      ],
    });
  }

  // ── dot: single-series dot chart (fallback for simple comparisons) ──
  const showLabels = config.show_value_labels !== false;
  const dotVals = data.map((row) => Number(row[config.y])).filter((v) => Number.isFinite(v));
  const dotVMin = Math.min(...dotVals, 0);
  const dotVMax = Math.max(...dotVals, 0);
  const dotPad = Math.max((dotVMax - dotVMin) * 0.08, Math.abs(dotVMin) * 0.15, 0.3);
  return Plot.plot({
    ...common,
    x: {
      ...common.x,
      domain: [dotVMin - dotPad, dotVMax + dotPad],
      tickFormat: (value: number) => formatter.format(value),
      ...(axisMax != null ? { domain: [axisMin ?? 0, axisMax] } : {}),
    },
    y: { ...common.y, domain: data.map((row) => String(row[config.x])) },
    marks: [
      Plot.dot(data, {
        x: config.y,
        y: config.x,
        fill: (row: Record<string, string | number>) => {
          const key = String(row[config.series ?? config.x]);
          // If a color_map exists but lacks this key, use the neutral contrast
          // (gray) so only mapped series carry the accent.
          return config.color_map ? (config.color_map[key] ?? contrast) : accent;
        },
        r: theme.dotRadiusLarge,
        tip: true,
      }),
      ...(showLabels
        ? [Plot.text(data, {
            x: config.y,
            y: config.x,
            text: (row: Record<string, string | number>) => formatter.format(Number(row[config.y])),
            dx: 12,
            textAnchor: "start",
            fill: ink,
            fontWeight: theme.valueLabelWeight,
            fontSize: theme.valueLabelSize,
          })]
        : []),
      Plot.ruleX([0], { stroke: muted }),
      // Reference/parity line (e.g. ratio 1.0): dashed so it reads as a
      // benchmark, not a data mark.
      ...(config.reference != null && config.reference !== 0
        ? [Plot.ruleX([config.reference], { stroke: muted, strokeDasharray: "6,4", strokeWidth: theme.strokeWidthThin })]
        : []),
      ...annotationMarks(),
    ],
  });
}

const chartRootElement = document.querySelector<HTMLElement>("#chart");
if (!chartRootElement) throw new Error("Missing chart root");
const chartRoot: HTMLElement = chartRootElement;

function insetAxisLabels(svg: SVGSVGElement): void {
  // Dot charts render the value-axis label on the left edge, and at the 480px
  // floor it can sit flush against the SVG boundary. Nudge the y-axis label
  // group inward by 4px so the rotated label has a clear inset (2c regression).
  if (config.chart_type !== "dot") return;
  const yLabelGroup = svg.querySelector<SVGGElement>('g[aria-label="y-axis label"]');
  if (!yLabelGroup) return;
  const transform = yLabelGroup.getAttribute("transform");
  if (!transform) return;
  const match = /translate\(([-\d.]+),\s*([-\d.]+)\)/.exec(transform);
  if (!match) return;
  const x = parseFloat(match[1]!);
  const y = parseFloat(match[2]!);
  yLabelGroup.setAttribute("transform", `translate(${x + 4}, ${y})`);
}

function minChartWidth(): number {
  // Compact mode: charts whose MARKS compress safely — few
  // bands and short category labels — may render down to 360px and let Plot
  // rescale the marks; the 480px floor exists to protect TEXT, not marks.
  // Dense charts (50-dot strips, choropleths, facets, grouped bars, and
  // bars with long labels) keep the 480px floor and the container's
  // horizontal scroll (.chart{overflow-x:auto} at <=520px).
  const COMPACT_TYPES = new Set(["arrow", "dot", "lollipop", "ratio_ladder", "dumbbell"]);
  if (COMPACT_TYPES.has(config.chart_type)) return 360;
  if (config.chart_type === "bar" && !config.series && config.orientation === "horizontal") {
    const bands = new Set(data.map((row) => String(row[config.x]))).size;
    const longest = Math.max(...data.map((row) => String(row[config.x]).length), 0);
    if (bands <= 6 && longest <= 16) return 360;
  }
  return 480;
}

function render(): void {
  // Charts are designed at desktop density; on narrow screens the container
  // CSS (.chart{overflow-x:auto} at <=520px) scrolls any overflow. Charts
  // that can compress safely use the compact floor (360px); the rest keep
  // the 480px legibility floor so text is never crushed.
  const width = Math.max(minChartWidth(), Math.floor(chartRoot.getBoundingClientRect().width));
  const node = chartForWidth(width);
  chartRoot.replaceChildren(node);
  if (node instanceof SVGSVGElement) {
    insetAxisLabels(node);
    requestAnimationFrame(() => {
      try {
        const qa = runQa(node);
        if (!qa.passed) {
          console.warn("[chart-qa] FAIL:", JSON.stringify(qa.checks.filter((c: { status: string }) => c.status === "fail")));
        }
      } catch (e) {
        // getBBox can throw if SVG not yet laid out; skip silently
      }
    });
  }
}

const tableBody = document.querySelector<HTMLTableSectionElement>("#data-body");
if (tableBody) {
  const rowKey = config.chart_type === "choropleth" ? (config.region_key ?? "region") : config.x;
  const columns = config.series ? [rowKey, config.series, config.y] : [rowKey, config.y];
  // Must mirror render.mjs's header: CI bounds appended when present.
  if (config.ci_low && config.ci_high) {
    columns.push(config.ci_low, config.ci_high);
  }
  for (const row of data) {
    const tr = document.createElement("tr");
    for (const key of columns) {
      const td = document.createElement("td");
      // Fallback-table fidelity: the table is the reader's source of truth
      // for the underlying numbers, so value cells must carry the FULL
      // precision present in data.csv — not the chart's axis rounding
      // (formatter.format applies maximumFractionDigits: 1, which renders
      // gdp_trillions 1.619 as "1.6"). Grouped digits keep large raw values
      // legible without changing any digits. Category/series cells stay
      // verbatim from the CSV.
      td.textContent =
        key === config.y || key === config.ci_low || key === config.ci_high
          ? new Intl.NumberFormat("en-US", { maximumFractionDigits: 20 }).format(Number(row[key]))
          : String(row[key]);
      tr.append(td);
    }
    tableBody.append(tr);
  }
}

// The ResizeObserver that re-renders on container resize is registered at the
// bottom of this file (renderAndRearm) so every redraw re-arms the interaction
// layer; do not register another observer here.

// ── Interaction runtime: affordance, keyboard access, tooltip mirroring ─
// One enhancement layer attached to #chart after each (re)render:
//   1. Mobile scroll affordance — right-edge gradient cue + "drag to explore"
//      pill when the SVG overflows its scroll container (the 480px legibility
//      floor can exceed narrow viewports). Dismissed permanently on the first
//      real scroll/touch; prefers-reduced-motion hides instantly (CSS also
//      kills all animation/transition under reduce).
//   2. Keyboard access — roving tabindex over Plot's mark groups (the g[aria-label]
//      groups Plot emits per mark; axis/frame groups carry structural labels and
//      are skipped), Enter/Space re-pins that mark's tip content into an aria-live
//      region ("tooltip text mirrored politely").
//   3. Tooltip performance — pointermove coalesced through requestAnimationFrame.
// Plot already renders tips natively (tip: true) with sticky-click support and
// even rAF-batches FACETED re-renders internally (pointer.js facetState); this
// layer adds what it does NOT provide: focusability, non-pointer activation,
// and screen-reader announcement.
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");

const liveRegion = document.createElement("div");
liveRegion.className = "chart-live-region";
liveRegion.setAttribute("role", "status");
liveRegion.setAttribute("aria-live", "polite");
liveRegion.setAttribute("aria-atomic", "true");
// Visually hidden but visible to screen readers (classic clip pattern; safe
// under prefers-reduced-motion since it never animates).
liveRegion.style.cssText =
  "position:absolute;width:1px;height:1px;margin:-1px;padding:0;border:0;" +
  "clip:rect(0 0 0 0);clip-path:inset(50%);overflow:hidden;white-space:nowrap";

function applyRovingTabindex(markGroups: Element[]): void {
  const n = markGroups.length;
  for (let i = 0; i < n; i++) {
    const group = markGroups[i] as HTMLElement & { setAttribute: (k: string, v: string) => void };
    group.setAttribute("tabindex", i === 0 ? "0" : "-1");
    if (!group.getAttribute("role")) group.setAttribute("role", "button");
    // Screen-reader label from data semantics, not Plot internals.
    const row = data[i];
    if (row) {
      const parts = [config.x, config.y]
        .filter((k): k is string => Boolean(k))
        .map((k) => `${k}: ${row[k]}`);
      const seriesVal = config.series ? String(row[config.series]) : undefined;
      group.setAttribute(
        "aria-label",
        parts.join(", ") + (seriesVal ? `, ${config.series}: ${seriesVal}` : ""),
      );
    }
  }
}

function moveTabindex(from: Element, to: Element): void {
  from.setAttribute("tabindex", "-1");
  to.setAttribute("tabindex", "0");
  (to as HTMLElement).focus({ preventScroll: true });
}

// Point-to-index lookup shared by pointer and keyboard paths.
function nearestIndex(plot: SVGSVGElement, x: number, y: number): number {
  let best = -1;
  let bestD = Infinity;
  markBoxes(plot).forEach((box, i) => {
    const dx = Math.max(box.left - x, 0, x - box.right);
    const dy = Math.max(box.top - y, 0, y - box.bottom);
    const d = dx * dx + dy * dy;
    if (d < bestD) { bestD = d; best = i; }
  });
  return bestD < 60 * 60 ? best : -1;
}

type Box = { left: number; top: number; right: number; bottom: number };

function markBoxes(plot: SVGSVGElement): Box[] {
  return markGroupSelector === null
    ? []
    : Array.from(plot.querySelectorAll<SVGGElement>(markGroupSelector)).map((g) => {
        const r = g.getBoundingClientRect();
        return { left: r.left, top: r.top, right: r.right, bottom: r.bottom };
      });
}

let markGroupSelector: string | null = null;

interface ScrollAffordance {
  cue: HTMLDivElement;
  pill: HTMLDivElement;
}

const affordances = new WeakMap<HTMLElement, ScrollAffordance>();
let affordanceDismissed = false; // permanent across re-renders

function buildScrollAffordance(wrapper: HTMLElement): void {
  wrapper.style.position = wrapper.style.position || "relative";
  const cue = document.createElement("div");
  cue.className = "scroll-cue";
  const pill = document.createElement("div");
  pill.className = "scroll-hint";
  pill.textContent = "drag to explore";
  const fade = () => {
    affordanceDismissed = true;
    cue.remove();
    pill.remove();
  };
  if (!affordanceDismissed) {
    wrapper.addEventListener("scroll", fade, { once: true, capture: true });
    wrapper.addEventListener("touchstart", fade, { once: true, capture: true });
    wrapper.addEventListener("wheel", fade, { once: true, capture: true });
  }
  affordances.set(wrapper, { cue, pill });
}

function updateScrollAffordance(wrapper: HTMLElement, overflowNow: boolean): void {
  const a = affordances.get(wrapper);
  if (!a) return;
  if (affordanceDismissed || !overflowNow) {
    if (a.cue.parentNode) a.cue.remove();
    if (a.pill.parentNode) a.pill.remove();
    return;
  }
  if (!a.cue.parentNode) wrapper.appendChild(a.cue);
  if (!a.pill.parentNode) wrapper.appendChild(a.pill);
}

function setupInteractions(): void {
  // NOTE: chartKeydown is hoisted to module scope so this removeEventListener
  // actually matches the handler added below (function-declaration bindings
  // inside this block would be a no-op removal and stack duplicate listeners
  // on re-render).
  chartRoot.querySelectorAll(".scroll-cue,.scroll-hint").forEach((el) => el.remove());
  chartRoot.removeEventListener("keydown", chartKeydown);

  const svgs = Array.from(chartRoot.querySelectorAll<SVGSVGElement>("svg"));
  const plotMaybe = svgs.sort((a, b) =>
    (b.getBoundingClientRect().width * b.getBoundingClientRect().height) -
    (a.getBoundingClientRect().width * a.getBoundingClientRect().height))[0];
  if (!plotMaybe) return;
  const plot: SVGSVGElement = plotMaybe;
  // Roving tabindex over Plot's per-mark ARIA groups. Structural groups in
  // every renderer axis use aria-labels like "x-axis", "y-axis", "y-grid",
  // "y-axis label"; those are excluded below so only data marks tab.
  const excludedLabels = /^(x|y|fx|fy|color|opacity|r)-(axis|axis label|grid|tick)$/;
  const groups = Array.from(plot.querySelectorAll<SVGGElement>("g[aria-label]")).filter((g) => {
    const label = g.getAttribute("aria-label") ?? "";
    if (excludedLabels.test(label)) return false;
    return !g.querySelector("path,rect,circle,line,polygon") ? false : g.childElementCount > 0 && !label.endsWith("-label") && !label.includes("tick");
  });
  if (groups.length > 0) {
    markGroupSelector = "g[aria-label]";
    applyRovingTabindex(groups);
  } else {
    markGroupSelector = null;
  }

  function chartKeydown(ev: KeyboardEvent): void {
    const target = ev.target as Element;
    const current = groups.indexOf(target as SVGGElement);
    if (current < 0) return;
    if (ev.key === "ArrowRight" || ev.key === "ArrowDown") {
      ev.preventDefault();
      moveTabindex(groups[current]!, groups[(current + 1) % groups.length]!);
    } else if (ev.key === "ArrowLeft" || ev.key === "ArrowUp") {
      ev.preventDefault();
      moveTabindex(groups[current]!, groups[(current - 1 + groups.length) % groups.length]!);
    } else if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      announce(current);
    }
  }
  chartRoot.addEventListener("keydown", chartKeydown);

  function announce(index: number): void {
    const row = data[index];
    if (!row) return;
    // Mirror the focused mark's tooltip-equivalent text into the polite
    // aria-live region (never assertive — nothing here is urgent).
    liveRegion.textContent = [config.x, config.y]
      .filter((k): k is string => Boolean(k))
      .map((k) => `${k} ${row[k]}`)
      .join(", ");
  }

  // ── Pointer → live-region mirror with rAF coalescing ─────────────────
  // Plot 0.6.17 coalesces faceted re-renders with rAF inside pointer.js, but
  // non-faceted plots render synchronously per pointermove event. Our mirror
  // listener throttles hover announcements to one update per frame; the
  // nearest-mark lookup runs inside that frame callback, not per event.
  let pendingFrame: number | null = null;
  let pendingPoint: { x: number; y: number } | null = null;
  let pendingLeave = false;

  function scheduleMirror(ev: PointerEvent | null): void {
    if (ev) {
      const rect = plot.getBoundingClientRect();
      pendingPoint = { x: ev.clientX - rect.left, y: ev.clientY - rect.top };
    } else {
      pendingLeave = true;
    }
    if (pendingFrame != null) return;
    pendingFrame = window.requestAnimationFrame(() => {
      pendingFrame = null;
      if (pendingLeave) { pendingLeave = false; liveRegion.textContent = ""; return; }
      const p = pendingPoint;
      pendingPoint = null;
      if (!p || markGroupSelector === null || groups.length === 0) return;
      const boxes = Array.from(plot.querySelectorAll<SVGGElement>(markGroupSelector)).map((g) => g.getBoundingClientRect());
      const pr = plot.getBoundingClientRect();
      let best = -1;
      let bestD = Infinity;
      boxes.forEach((b, i) => {
        const dx = Math.max(b.left - p.x - pr.left, 0, p.x + pr.left - b.right);
        const dy = Math.max(b.top - p.y - pr.top, 0, p.y + pr.top - b.bottom);
        const d = dx * dx + dy * dy;
        if (d < bestD) { bestD = d; best = i; }
      });
      if (best >= 0 && bestD < 60 * 60) announce(best);
    });
  }

  plot.addEventListener("pointermove", scheduleMirror, { passive: true });
  plot.addEventListener("pointerleave", () => scheduleMirror(null), { passive: true });

  // ── Scroll affordance wiring ────────────────────────────────────────
  // The overflow container itself depends on viewport CSS (.chart gets
  // overflow-x:auto at <=520px), so measure chartRoot scrollWidth vs
  // clientWidth rather than hardcoding breakpoints. Detected post-layout
  // (rAF), because styles must be applied before overflow exists.
  buildScrollAffordance(chartRoot);
  requestAnimationFrame(() => {
    updateScrollAffordance(chartRoot, chartRoot.scrollWidth > chartRoot.clientWidth);
  });
}

setupInteractions();
document.body.appendChild(liveRegion);

// ── Scroll-reveal "unfold" ─────────────────────────────────────────────
// The interactions layer above is (re)armed AFTER each render() — see the
// setupInteractions() call following render() at the bottom of this file,
// because render() calls chartRoot.replaceChildren(), which destroys any
// previously injected affordance/keyboard DOM. The call here covers nothing
// today (no render has run yet) but keeps this block safe if invocation
// order moves.
// The scroll-reveal "unfold": premium editorial reveal — the chart draws
// itself in (clip-path unfold + rise + fade) when the reader scrolls to it.
// In the explorer the PARENT page scrolls (charts sit in auto-sized srcdoc
// iframes), so the parent posts "chart:reveal" into each iframe; standalone
// charts arm the same reveal with their own IntersectionObserver. Failsafe:
// the chart is fully visible unless .reveal-play is added, and a hard timeout
// guarantees the class is always removed.
// ── Choreography: classify the plot's marks and stagger them in ────────
// Bars grow from the zero baseline (negative bars grow downward), dots pop
// with an overshoot, stems/arrows draw themselves, choropleth states fade,
// value labels fade up. Delay ramps in reading order (band/category axis),
// so the chart "unfolds" like an editorial piece rather than flashing in.
// `chart-settled` fires when the last animation ends (failsafe timeout),
// so the rasterizer never captures a mid-animation frame.
function choreograph(root: HTMLElement): void {
  // Plot svg = the LARGEST svg in #chart (legend swatches are tiny by
  // comparison). Plot's classes are hashed (plot-d6a7b5), so select by
  // size, not class.
  const svgs = Array.from(root.querySelectorAll("svg"));
  const plot = svgs.sort((a, b) => {
    const wa = a.getBoundingClientRect().width * a.getBoundingClientRect().height;
    const wb = b.getBoundingClientRect().width * b.getBoundingClientRect().height;
    return wb - wa;
  })[0] as SVGSVGElement | null;
  const settle = () => {
    root.classList.remove("reveal-play");
    (root as any).__chartSettled = true;
    root.dispatchEvent(new CustomEvent("chart-settled"));
    // Keep the property alive for external auditors even if the bundler's
    // minifier tries to drop assignments it cannot prove are read.
    void (root as any).__chartSettled;
  };
  if (!plot) { settle(); return; }

  // Zero baseline derived from the MARKS themselves: bars/stems share one
  // edge (the zero line) — positive marks extend from it one way, negative
  // the other. The mode of all mark edges IS the baseline; axis spines are
  // unique values and lose the vote. This is geometry-only, so it works for
  // every orientation without knowing axis directions.
  const edgesX = new Map<number, number>();
  const edgesY = new Map<number, number>();
  const bump = (m: Map<number, number>, v: number) => { if (Number.isFinite(v)) m.set(v, (m.get(v) ?? 0) + 1); };
  const mode = (m: Map<number, number>): number | null => {
    let best: number | null = null, bestN = 0;
    for (const [v, n] of m) if (n > bestN) { bestN = n; best = v; }
    return bestN >= 2 ? best : null;
  };
  const rects = Array.from(plot.querySelectorAll("rect"));
  for (const r of rects) {
    const x = parseFloat(r.getAttribute("x") ?? "NaN");
    const y = parseFloat(r.getAttribute("y") ?? "NaN");
    const w = parseFloat(r.getAttribute("width") ?? "NaN");
    const h = parseFloat(r.getAttribute("height") ?? "NaN");
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(w) || !Number.isFinite(h) || w <= 0 || h <= 0) continue;
    bump(edgesX, x); bump(edgesX, x + w);
    bump(edgesY, y); bump(edgesY, y + h);
  }
  const lines = Array.from(plot.querySelectorAll("line"));
  for (const ln of lines) {
    const x1 = parseFloat(ln.getAttribute("x1") ?? "NaN");
    const y1 = parseFloat(ln.getAttribute("y1") ?? "NaN");
    const x2 = parseFloat(ln.getAttribute("x2") ?? "NaN");
    const y2 = parseFloat(ln.getAttribute("y2") ?? "NaN");
    if (Number.isFinite(x1)) bump(edgesX, x1);
    if (Number.isFinite(x2)) bump(edgesX, x2);
    if (Number.isFinite(y1)) bump(edgesY, y1);
    if (Number.isFinite(y2)) bump(edgesY, y2);
  }
  const zeroX = mode(edgesX);
  const zeroY = mode(edgesY);

  const delayed = new Map<SVGElement, number>();
  const labels: SVGElement[] = [];
  let delay = 0;
  const D = 80; // ms per mark — slow enough to feel editorial
  const MAX_STAGGER_MS = 3200; // dense line charts must still settle promptly
  let maxDelay = 0;
  const push = (el: SVGElement, step: number, cls: string) => {
    el.classList.add(cls);
    const d = Math.min(delay * D, MAX_STAGGER_MS);
    delayed.set(el, d);
    maxDelay = Math.max(maxDelay, d);
    delay += step;
  };

  const classify = (el: SVGElement) => {
    const tag = el.tagName;
    if (tag === "rect") {
      const w = parseFloat(el.getAttribute("width") ?? "0");
      const h = parseFloat(el.getAttribute("height") ?? "0");
      if (w <= 2 || h <= 2) return; // tick stubs
      const fill = el.getAttribute("fill") ?? "none";
      if (fill === "none" || fill === "transparent") return; // plot frame
      const x = parseFloat(el.getAttribute("x") ?? "0");
      const y = parseFloat(el.getAttribute("y") ?? "0");
      if (w > h) {
        // Horizontal bar (barX): value along x, grows from the zero line.
        el.style.transformOrigin = zeroX != null && Math.abs(zeroX - (x + w)) < 1 ? "100% 50%" : "0% 50%";
        push(el, 1, "anim-bar-h");
      } else {
        // Vertical bar (barY): value along y, grows from the zero line.
        el.style.transformOrigin = zeroY != null && Math.abs(zeroY - y) < 1 ? "50% 0%" : "50% 100%";
        push(el, 1, "anim-bar-v");
      }
    } else if (tag === "circle") {
      const r = parseFloat(el.getAttribute("r") ?? "0");
      if (r < 1.5) return;
      push(el, 1, "anim-dot");
    } else if (tag === "path") {
      const fill = el.getAttribute("fill") ?? "none";
      const isMapFill = fill !== "none" && fill !== "transparent";
      if (isMapFill) {
        push(el, 0.05, "anim-map"); // whole map washes in quickly
      } else if (el.getAttribute("marker-end")) {
        push(el, 1, "anim-arrow");
      } else {
        const path = el as SVGPathElement;
        const len = path.getTotalLength ? path.getTotalLength() : 0;
        if (len > 8) push(el, 1, "anim-stem");
      }
    } else if (tag === "line") {
      const x1 = parseFloat(el.getAttribute("x1") ?? "NaN");
      const y1 = parseFloat(el.getAttribute("y1") ?? "NaN");
      const x2 = parseFloat(el.getAttribute("x2") ?? "NaN");
      const y2 = parseFloat(el.getAttribute("y2") ?? "NaN");
      const len = Math.hypot(x2 - x1, y2 - y1);
      // Data stems are HORIZONTAL lines anchored at the zero line (lollipops,
      // 3b). Vertical lines (ticks, spines, gridlines) are always structure —
      // no chart in this set has vertical data lines.
      const horizontal = Math.abs(y1 - y2) < 1;
      const anchored = zeroX != null && (Math.abs(x1 - zeroX) < 2 || Math.abs(x2 - zeroX) < 2);
      if (horizontal && anchored && len > 40 && len < 800) push(el, 1, "anim-stem");
    } else if (tag === "text") {
      labels.push(el);
    }
  };

  const walk = (node: Element) => {
    if (node.tagName === "g" || node.tagName === "svg") {
      for (const child of Array.from(node.children)) walk(child);
    } else {
      classify(node as SVGElement);
    }
  };
  walk(plot);

  // Value labels fade up after the marks land. CRITICAL: never animate
  // `transform` on SVG text — the CSS transform OVERRIDES the element's
  // translate(x,y) attribute (SVG2 CSS-transforms precedence), collapsing
  // every label to the SVG origin until the animation ends (the "labels pile
  // in the top-left corner" bug). Use the individual `translate` property,
  // which COMPOSES with the attribute transform; see render.mjs @keyframes
  // anim-label.
  for (const lab of labels) {
    lab.classList.add("anim-label");
    delayed.set(lab, maxDelay + 250);
  }

  for (const [el, d] of delayed) el.style.setProperty("--d", `${d}ms`);

  // Settled: last mark + label delay + animation + headroom.
  const total = maxDelay + 250 + 700 + 300;
  window.setTimeout(settle, total);
}

function armReveal(): void {
  const el = chartRoot;
  if (el.dataset.reveal === "armed") return;
  el.dataset.reveal = "armed";
  const play = () => {
    if (el.dataset.reveal === "played") return;
    el.dataset.reveal = "played";
    el.classList.add("reveal-play");
    choreograph(el);
  };
  // 1. Parent-driven (explorer embeds charts in srcdoc iframes).
  window.addEventListener("message", (ev: MessageEvent) => {
    if (ev.data === "chart:reveal") play();
  });
  // 2. Standalone fallback: own viewport visibility. Only when NOT embedded —
  //    explorer iframes are auto-sized to full content, so an in-iframe
  //    observer would fire on load and defeat the parent-driven scroll reveal.
  const embedded = (() => {
    try { return window.self !== window.top; } catch { return true; }
  })();
  if (!embedded && typeof IntersectionObserver !== "undefined") {
    const io = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          play();
          io.disconnect();
        }
      }
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.05 });
    io.observe(el);
  } else if (!embedded) {
    play();
  }
}
armReveal();
render();
// The render() above replaceChildren()s the chart — re-arm the interactions
// layer (keyboard roving tabindex, pointer mirror listeners, scroll-affordance
// DOM) against the freshly rendered SVG. Subsequent ResizeObserver-driven
// re-renders re-arm through the wrapped observer below so the affordance and
// keyboard targets survive every resize-triggered redraw.
setupInteractions();
const renderAndRearm = (): void => {
  render();
  setupInteractions();
};
new ResizeObserver(renderAndRearm).observe(chartRoot);

