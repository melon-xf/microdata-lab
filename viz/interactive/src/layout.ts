// ──────────────────────────────────────────────────────────────────────
// Layout Engine — computes the spatial budget for every chart element.
// Title, subtitle, legend, plot area, value labels, and footer each get
// a non-overlapping rectangle. No branch computes its own margins.
// ──────────────────────────────────────────────────────────────────────

import type { ThemeTokens } from "./tokens";
import { computeDimensions } from "./tokens";

export interface ChartLayout {
  // Outer container
  width: number;
  height: number;

  // Named regions (all relative to the SVG viewport)
  title: { x: number; y: number; maxWidth: number };
  subtitle: { x: number; y: number; maxWidth: number };
  legend: { x: number; y: number; maxWidth: number; slotHeight: number };
  plot: {
    x: number; y: number; width: number; height: number;
    marginTop: number; marginRight: number;
    marginBottom: number; marginLeft: number;
  };
  footer: { x: number; y: number; maxWidth: number };
}

// Line height constants (relative to font size)
const LH = 1.35;
const HEADLINE_LH = 1.0;

/**
 * Compute a layout given the chart width, the number of data bands
 * (categories on the primary axis), and whether a legend is needed.
 * Every element gets an explicit position so nothing overlaps.
 */
export function computeLayout(
  containerWidth: number,
  chartType: string,
  theme: ThemeTokens,
  options: {
    hasLegend?: boolean;
    hasValueLabels?: boolean;
    nCategories?: number;
    isHorizontal?: boolean;
  } = {},
): ChartLayout {
  const { width, height } = computeDimensions(containerWidth, chartType);

  const padding = 40; // outer page padding (matching CSS main padding)
  const innerW = width - padding * 2;

  // Vertical budget (top to bottom):
  //   title → subtitle → [legend] → plot → source line
  let cursorY = padding;

  // Title
  const titleH = theme.headlineSize * HEADLINE_LH;
  const title = { x: padding, y: cursorY + theme.headlineSize, maxWidth: innerW };
  cursorY += titleH + 6;

  // Subtitle
  const subtitleH = theme.subtitleSize * LH;
  const subtitle = { x: padding, y: cursorY + theme.subtitleSize, maxWidth: innerW };
  cursorY += subtitleH + theme.headerGap;

  // Legend (optional) — single row of swatch + label pairs
  let legend = { x: padding, y: 0, maxWidth: innerW, slotHeight: 0 };
  if (options.hasLegend) {
    const legendH = theme.legendFontSize * LH + 8;
    legend = { x: padding, y: cursorY + theme.legendFontSize, maxWidth: innerW, slotHeight: legendH };
    cursorY += legendH + 12;
  }

  // Plot area — fills remaining vertical space with a floor
  const footerH = theme.sourceSize * LH + 16;
  const sourceRuleGap = 14;
  const plotEnd = height - padding - footerH - sourceRuleGap;
  const plotHeight = Math.max(280, plotEnd - cursorY);

  // Plot margins (value labels need right padding; long category labels
  // need left padding on horizontal charts)
  const isHorizontal = options.isHorizontal ?? false;
  const labelPad = options.hasValueLabels ? 60 : 28;
  const marginLeft = isHorizontal ? 80 : 66;
  const marginRight = isHorizontal ? labelPad : 28;

  const plot = {
    x: padding,
    y: cursorY,
    width: innerW,
    height: plotHeight,
    marginTop: 12,
    marginRight,
    marginBottom: 52,
    marginLeft,
  };

  // Footer
  const footer = {
    x: padding,
    y: plot.y + plot.height + sourceRuleGap + theme.sourceSize,
    maxWidth: innerW,
  };

  return { width, height, title, subtitle, legend, plot, footer };
}
