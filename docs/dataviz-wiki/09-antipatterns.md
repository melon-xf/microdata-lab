# 09 — Anti-Patterns Catalog

The consolidated "never do this" list with each author's verdict.
S = Schwabish, C = Cairo, K = Knaflic, T = Tufte. **Bold** = enforced
as a hard validation error in this pipeline.

## Absolute bans

| Anti-pattern | Verdicts | Why |
|---|---|---|
| **3D charts** | K: "never use 3D" [doc 10]; S pp. 43–44; T | depth adds no data; projection reads 1.0 as 0.8 |
| **Pie charts** | K: "evil" [doc 10]; S: tolerable w/ rules [pp. 235–237] | angles/areas rank low on the encoding hierarchy; ordered bar wins every time |
| **Donut charts** | K: "Don't use donut charts" [doc 10] | arc length is worse than angle |
| **Dual y-axes** | K [doc 10]; S pp. 142–143 | manufactures spurious correlation |
| **Axis breaks** | S pp. 138–139 | distorts all comparisons |
| **Truncated bar axis** | K [doc 10]; S pp. 29–30 | length encodings must start at zero |
| **Rainbow palette** | S p. 68; K doc 12 | implies categories that don't exist; nothing stands out |
| **Red–green encoding** | K doc 12; S p. 68 | 8% of men can't see the difference |
| **Diagonal text** | K doc 11; S p. 371 | 45° = 52% slower; 90° = 205% slower |
| **Legend round-trips** | S p. 57; K doc 11 | breaks 4-chunk working memory; direct-label instead |
| **Raw counts on maps** | C pp. 255–256 | maps population, not the phenomenon |

## Strong discouragements

| Anti-pattern | Verdicts | Why |
|---|---|---|
| Spaghetti lines (>4–5 series) | S pp. 147–149; K doc 17; C pp. 24–26 | "informative as haphazard noodles"; use small multiples or highlight+gray |
| Bubble comparisons | C pp. 44–48; S p. 133 | readers compare diameters; underestimate differences |
| Area/stacked-stream for values | S pp. 143–145; K doc 10 | no baseline; pattern-only |
| Markers on every point | K doc 12 | clutter; sparing markers = "look here" |
| Center-aligned text | K doc 11 | no clean edge |
| Chart border + heavy gridlines | K doc 11; S pp. 58–59 | closure makes them redundant |
| Dark backgrounds | K doc 17 | heavy; pulls eyes from data |
| Trailing zeros / excess precision | K docs 11, 13 | fractions of a person |
| Icons scaled to value | S pp. 119–120 | height 2× → area 4× (Brinton 1914) |
| Animation while reading | C pp. 94–95 | peripheral motion hijacks attention |
| Slideuments | K doc 9 | serves neither live nor written audience |
| Re-sorting between linked views | K doc 17 | mental tax; keep base order, move emphasis |

## Judgment calls (context-dependent)

- **Chartjunk**: T's data-ink absolutism is softened by evidence —
  Bateman 2010 (via C pp. 66–67): "junk" versions were read equally
  well and remembered better. Verdict: minimal by default; delight
  permitted at zero accuracy cost.
- **Nonzero line baseline**: acceptable within bounds (⅓–2× data
  range), justify on the chart [S pp. 139–140].
- **Unlabeled axes**: only when relative shape is the entire point and
  omission is deliberate [K doc 13].
- **Novel/exotic forms**: allowed with redundancy scaffolding and a
  how-to-read key [C p. 83; S pp. 80–81].
