# 06 — Axes, Scales & Integrity

Sources: Schwabish ch. 2, 6 [S], Knaflic ch. 2 [K], Cairo ch. 5, 7
[C], Tufte [T].

## The zero-baseline rule (with the honest exception)

- **Bars/length: always zero.** "Bar charts… should always start at
  zero" — a nonzero origin converts a 13% change into a 460% visual
  change (Fox News) [K doc 10; S pp. 29–30].
- **Lines/dots: not required, but bounded and justified.** Tufte
  emphasized relative change over absolute origin; S's heuristic: y-range
  within ~⅓ to 2× the data range; if you deviate, say why on the chart
  [S pp. 139–140].
- Axis **breaks are never acceptable** [S pp. 138–139]; Norie's
  intentional-deception examples [S pp. 30–31].

## Scale choices

- **Log scales**: for multiplicative/ratio phenomena; always labeled
  as log; if the audience can't read logs, show the level instead
  [S pp. 140–142].
- **Dual y-axes: never.** Two series on two scales manufactures any
  correlation you want; alternatives: direct-label points, or two
  panels sharing the x-axis [K doc 10; S pp. 142–143].
- **Uniform time intervals** on x — decades then years is misleading
  [K doc 10].
- **Indexed/percent-change views**: declare the base period on the
  chart; % change loses magnitude — pair with levels when the base
  matters [K doc 10].

## Normalization — compute the derived variable first

- Totals mislead across unequal populations: per-capita, per-100k,
  share — BEFORE charting [C pp. 37–38; S p. 17].
- Derived difference/ratio IS often the story: don't make readers
  subtract two lines — plot the difference [C pp. 108–109];
  line-width illusion makes converging curves lie [S pp. 149–150].
- pp vs % always explicit [S pp. 21–22].
- Maps: raw counts on a choropleth are a validation error; age/risk
  adjustment when the denominator's composition varies (Rosling's
  heart-attack map) [C pp. 255–256].

## Uncertainty (see also 02-H)

- **CI whiskers/error bars are BANNED (user directive 2026-08).** Point
  estimates only; interval bounds live in the fallback data table so
  statistical claims ("CIs overlap", "not significant") stay verifiable
  without drawing them. (Supersedes the earlier "show intervals" guidance
  below.)
- Label WHAT the interval is (95% CI vs SE vs min–max) [S p. 202] — in the
  table, not on the chart.
- Suppress or flag statistically unreliable cells (small n) rather than
  plotting them as equals.

## Missing & sparse data

- Line gaps stay visible (closure illusion fills them silently)
  [S p. 152].
- Missing categories get noted, not silently dropped.

## Tufte's integrity layer

- **Lie factor** = size of effect shown / size of effect in data; keep
  ≈1 [T ch. 2].
- **Data-ink ratio**: maximize ink that shows data; erase
  non-data-ink — but within reason (gridlines and frames can aid
  reading; evidence says mild "chartjunk" is harmless and memorable
  [C pp. 66–67]).
- **Show the data**: "People are reading your graph to learn something,
  and they do that best by seeing the data" [S p. 393].

## Renderer checklist

- [ ] Zero baseline enforced for all length encodings
- [ ] Line y-range within bounds or justified in subtitle
- [ ] No dual axes; no axis breaks; no truncated bars
- [ ] Normalization declared in config; raw-count maps rejected
- [ ] Time intervals uniform; log scales labeled
- [ ] Uncertainty encoding declared when CIs exist in data
- [ ] Missing data rendered as visible gaps
- [ ] Lie factor ≈ 1 (axis scaling vs data effect)
