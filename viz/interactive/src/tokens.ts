// ──────────────────────────────────────────────────────────────────────
// Design Tokens — single source of truth for all chart visuals.
// Every chart type, every theme, every size reads from here. Change a
// value once, it propagates everywhere. No scattered hex codes.
// ──────────────────────────────────────────────────────────────────────

export interface ThemeTokens {
  // Surfaces
  paper: string;
  ink: string;
  muted: string;
  hairline: string;
  rule: string;

  // Accent + semantic series colors
  accent: string;
  accentFill: string;       // translucent version of accent for fills
  contrast: string;         // grey for the comparison series
  contrastFill: string;

  // Data scale (sequential, used by choropleth etc.)
  scaleDomain: string[];    // e.g. ["#FCF0F1", ..., "#E30613"]

  // Categorical palette for multi-series charts (by series index)
  categoryPalette: string[];

  // Typography
  fontStack: string;
  headlineStack: string;
  headlineWeight: number;
  eyebrowFont: string;

  // Sizing (px) — relative to a base unit
  baseFontSize: number;     // axis labels, tick text
  headlineSize: number;
  subtitleSize: number;
  sourceSize: number;
  legendFontSize: number;
  valueLabelSize: number;
  valueLabelWeight: number;  // 700 for bold labels
  axisLabelWeight: number;   // 400 for quiet axis labels
  annotationSize: number;    // callout / bracket labels
  annotationWeight: number;

  // Stroke widths
  strokeWidth: number;      // main data line
  strokeWidthThin: number;  // gridlines, connectors
  strokeWidthThick: number; // emphasis lines, baselines
  dotRadius: number;
  dotRadiusSmall: number;   // secondary dots (strip dots, etc.)
  dotRadiusLarge: number;   // emphasis dots (subject series)

  // Spacing (px)
  margin: { top: number; right: number; bottom: number; left: number };
  headerGap: number;        // gap between subtitle and chart
  footerGap: number;        // gap between chart and source line
  labelGap: number;         // gap between value label and bar/dot end
  bracketGap: number;        // gap between bracket annotation and mark
}

// ── Swiss theme (editorial / newsroom) ──────────────────────────────
const swissBase = {
  paper: "#ffffff",
  ink: "#111111",
  muted: "#6e6e6e",
  hairline: "#e8e8e8",
  rule: "#d8d8d8",
  accent: "#e30613",
  accentFill: "#f2c9cc",
  contrast: "#6e6e6e",     // grey for the comparison series (matches verified output)
  contrastFill: "#ececec",
  fontStack: '"Helvetica Neue", Helvetica, Arial, sans-serif',
  headlineStack: '"Helvetica Neue", Helvetica, Arial, sans-serif',
  headlineWeight: 700,
  eyebrowFont: '"Helvetica Neue", Helvetica, Arial, sans-serif',
  baseFontSize: 14,
  headlineSize: 42,
  subtitleSize: 18,
  sourceSize: 13,
  legendFontSize: 13,
  valueLabelSize: 13,
  valueLabelWeight: 700,
  axisLabelWeight: 400,
  annotationSize: 12,
  annotationWeight: 600,
  strokeWidth: 3,
  strokeWidthThin: 1.5,
  strokeWidthThick: 4.5,
  dotRadius: 6,
  dotRadiusSmall: 4.5,
  dotRadiusLarge: 7.5,
  margin: { top: 24, right: 82, bottom: 56, left: 72 },
  headerGap: 28,
  footerGap: 24,
  labelGap: 8,
  bracketGap: 6,
};

// ── Default (teal-on-cream, softer) ─────────────────────────────────
const defaultBase = {
  ...swissBase,
  paper: "#fcfcfa",
  ink: "#17212b",
  muted: "#64717d",
  hairline: "#eef1f3",
  rule: "#d9dee2",
  accent: "#008c95",
  accentFill: "#bfe4e6",
  contrast: "#94a3ad",
  contrastFill: "#dde6ea",
  fontStack: 'Roboto, "Helvetica Neue", Arial, sans-serif',
  headlineStack: '"Roboto Condensed", Roboto, sans-serif',
  headlineWeight: 800,
};

// ── Editorial theme (warm paper, Jost typeface) ─────────────────────
const editorialBase = {
  ...defaultBase,
  paper: "#f8f7f5",
  ink: "#111111",
  muted: "#333333",
  rule: "#d9d9d9",
  accent: "#c4452b",
  accentFill: "#f0d8d0",
  headlineWeight: 900,
  fontStack: '"Jost", "Helvetica Neue", Arial, sans-serif',
  headlineStack: '"Jost Black", "Jost", "Helvetica Neue", Arial, sans-serif',
};

// ── Bauhaus (primary colors, black frame) ───────────────────────────
const bauhausBase = {
  ...defaultBase,
  paper: "#faf9f6",
  ink: "#0a0a0a",
  muted: "#8a8a8a",
  rule: "#0a0a0a",
  accent: "#e63900",
  accentFill: "#ffd6cc",
  headlineWeight: 900,
  fontStack: '"Jost", "Helvetica Neue", Arial, sans-serif',
  headlineStack: '"Jost Black", "Jost", sans-serif',
};

// Sequential red scale (light → dark) for choropleths
const redScale = [
  "#fcf0f1", "#f9dee0", "#f4c6c9", "#ee9ea3", "#e85b62", "#e30613",
];

// Swiss editorial categorical palette (red, blue, amber, green, ink)
const swissCategories = ["#E30613", "#2456E6", "#F5C400", "#1E8A3C", "#111111"];

const THEMES: Record<string, ThemeTokens> = {
  swiss: { ...swissBase, scaleDomain: redScale, categoryPalette: swissCategories },
  default: { ...defaultBase, scaleDomain: redScale.map(c => shiftToTeal(c)), categoryPalette: ["#008C95", "#2F6BFF", "#CB8214", "#4A7D5C", "#18354C"] },
  editorial: { ...editorialBase, scaleDomain: redScale, categoryPalette: ["#c34446", "#4e93b0", "#f6b781", "#a9c784", "#2d4d62"] },
  bauhaus: { ...bauhausBase, scaleDomain: redScale, categoryPalette: ["#E32636", "#2456E6", "#F5C400", "#0A0A0A", "#8A8A8A"] },
};

function shiftToTeal(hex: string): string {
  // Simple identity for now; can be replaced with an actual teal ramp
  return hex;
}

export function getTheme(name?: string): ThemeTokens {
  return THEMES[name ?? "swiss"] ?? THEMES["swiss"]!;
}

// ── Responsive sizing ────────────────────────────────────────────────
export function computeDimensions(width: number, chartType: string): {
  width: number;
  height: number;
} {
  const isTall = ["pictogram", "choropleth", "donut", "facet"].includes(chartType);
  const ratio = chartType === "facet" ? 1.6 : isTall ? 0.72 : 0.56;
  const maxH = chartType === "facet" ? 1800 : 720;
  return {
    width,
    height: Math.max(430, Math.min(maxH, Math.round(width * ratio))),
  };
}
