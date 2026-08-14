# 07 — Maps

Sources: Schwabish ch. 7 [S], Cairo ch. 4–5 + Rosling profile [C].

## First question: should this be a map?

S is the skeptic: maps are overused. "Should this be a map at all?" —
a ranked bar chart often answers the real question better
[S pp. 215–217]. Map only when the *geographic pattern itself* is the
claim (clusters, borders, policy regions). If the claim is "Texas is
highest," that's a bar chart. If the claim is "the whole Southeast is
a bloc," that's a map.

## Normalize before mapping (the cardinal rule)

- Raw counts on a choropleth = validation error [C pp. 255–256].
- Rosling's London heart-attack map: raw district rates mapped *where
  old people live*, not risk — "the designer must aggregate the initial
  microdata in a form that makes sense" [C pp. 255–256].
- Per-capita / rate / age-adjusted; declare the normalization in the
  subtitle.

## Choropleth craft

- Sequential single-hue ramp (light = low); diverging only with a
  meaningful midpoint; 3–9 bins if stepped [S pp. 222–223].
- Bins: quantiles vs equal-interval vs natural breaks — each tells a
  different story; pick deliberately and show the legend [S pp. 222–223].
- Never rainbow [S p. 68].
- Geographic size ≠ data importance: big empty states dominate. When
  that distorts the claim, use a **tile-grid** (equal-area squares) or
  **cartogram** [S pp. 226–228]; NYT pairs choropleth + cartogram +
  symbols for multidimensionality [C pp. 56–57].
- AK/HI/PR insets: albers-usa composite handles AK/HI; PR needs the
  composite or an explicit inset.

## Proportional symbols

- For point/place magnitudes; transparent + thin outline (overlaps stay
  readable); scale by AREA not radius; only for pattern, never precise
  reading [S pp. 224–226; C pp. 47–48].
- Bubbles on a choropleth: two variables, one geographic — acceptable
  for big-picture [C pp. 56–57].

## Projection & geometry (pipeline lessons)

- albers-usa for US national views (composite with AK/HI insets).
- **Topology matters**: simplify shared arcs ONCE (mapshaper), never
  per-feature (Douglas-Peucker per state diverges shared borders →
  white slivers; our UT/CO/WY/KS/TX/TN bug, fixed Aug 2026).
- d3-geo winding: CW exteriors in lon/lat; strip duplicate closing
  points; drop micro-islands that simplify to degenerate rings.
- Verify with `scripts/map_holes.py`: enclosed-white flood-fill scoped
  to the map bbox; largest component > 1,000 px = structural failure.

## Interaction

- Hover for exact values; the map gives pattern, the tooltip gives
  precision [S pp. 220–221].
- Click-to-filter links map to companion charts.

## Renderer checklist

- [ ] "Should this be a map?" answered in config comment
- [ ] Normalization declared (rate/per-capita/adjusted)
- [ ] Sequential ramp; bins justified; no rainbow
- [ ] Geographic-size distortion assessed → tile grid if needed
- [ ] Geometry from mapshaper pipeline only
- [ ] map_holes.py PASS on the rendered frame
- [ ] Hover values in interactive build
