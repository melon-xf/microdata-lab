# 11 — Renderer Rulebook

The testable rules the pipeline enforces. These are the "what never
ships" mechanics behind the doctrine pages — encoded as automated gates
so they cannot silently regress.

## Interactive renderer (TypeScript / Observable Plot)

`viz/interactive/` builds single-file HTML. Enforced by the analysis contract,
renderer regression tests, and browser audit gates.

- **No CI whiskers on marks.** Point estimates only; CI bounds go in the
  fallback data table. `tests/test_ci_whisker_ban.py` scans renderer
  source and chart configs; the interactive renderer must not emit
  error-bar marks and configs must not declare CI annotations
  (`test_no_ci_whisker_marks_in_interactive_renderer`,
  `test_no_errorbar_in_static_renderer`,
  `test_no_ci_annotations_in_chart_configs`).
- **Value-axis labels declared for horizontal-by-construction types.**
  Arrow, lollipop, strip, dot, dumbbell, ratio_ladder, and facet charts
  must declare `x_label`; omitting it silently drops the value-axis
  label (the "silent label drop" bug class).
- **No label collision in layout space.** Value labels and CI-endpoint
  annotations must not overlap; `data.csv` must carry the columns the
  config references.
- **Labels never pile at the SVG origin.** Text animation must not
  clobber each label's own `translate(x,y)` attribute (SVG2 CSS
  transform precedence) — animate the `translate` property, never
  `transform`, on SVG text.
- **Four-viewport cleanliness.** Every chart is audited at 375, 768,
  1280, and 1920 px: no clipping, collision, contrast, ordering,
  misleading-scale, or source-note-legibility failures
  (`viz/interactive/audit-labels.mjs`).
- **Reduced-motion honored.** `prefers-reduced-motion: reduce` must
  disable animation; scroll-reveal must not gate content visibility
  (charts are fully visible unless `.reveal-play` is added).
- **Accessible fallback.** Charts ship with a keyboard-accessible
  tabular fallback; tooltips are supplementary, never essential.

## Static renderer (R / ggplot2)

`viz/static/` + `scripts/bootstrap_r.sh` (micromamba R environment).
Enforced by `microdata viz gates` (68 gates across 17 analyses):

- **Deterministic re-render**: same inputs → byte-identical output (no
  timestamps, unseeded RNG, or unstable sorts).
- **Golden-image regression**: fresh render vs stored baseline within
  perceptual tolerance 0.02; hard fail at 0.2 (catches layout drift,
  clipping, blank figures).
- **Signal-color presence**: when chart.yaml declares `color`, the
  figure must contain pixels of it. Catches the blank-geometry defect
  class where a long title + long caption note compress the fixed-height
  ggplot panel until the data mark is pushed off-canvas — axes/title ink
  keeps content_frac healthy while the mark has zero pixels
  (`PIXEL_MIN_SIGNAL` in `src/microdata_lab/viz_gates.py`).
- **No error-bar marks** (whisker ban, static side).

### Static-canvas sizing

ggplot static figures use a fixed pixel canvas (`width`/`height` in
chart.yaml). Every text block — title (2 lines at 34px), subtitle (19px),
caption (source + note, wrapped at 95 chars) — eats vertical canvas.
Long titles *or* long notes can silently compress the plot panel to
zero height, pushing all geometry off-canvas with no R error. When the
signal-color gate fires or a figure looks empty:

- give the figure more canvas (e.g. `height: 1200` for a line chart with
  a long title + methodology note, `1900` for 51-row bar charts);
- shorten the subtitle to fit one line at 1600px width;
- re-render, vision-check, re-store the golden.

## Banned forms (both renderers)

Pie/donut/3D/dual-axis; pictograms; mental-subtraction ribbons; CI
whiskers on marks. Color is never the only encoding; truncated
quantitative axes require explicit justification.

## Verifying

```bash
uv run pytest                              # full suite incl. all gates above
uv run microdata viz gates                 # 68 gates across 17 analyses
node viz/interactive/audit-labels.mjs CHART.html WIDTH   # one chart, one width
node viz/interactive/audit-animation.mjs all             # motion at all widths
```
