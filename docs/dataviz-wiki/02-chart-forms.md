# 02 — Chart-Form Encyclopedia

Organized by **claim shape** (what the chart must prove), then ranked
within each shape by perceptual accuracy. Sources: Schwabish's
8-category taxonomy [S ch. 4–11], Cairo's task-constrains-form [C],
Knaflic's business taxonomy [K ch. 2], Tufte [T].

**Selection meta-rules**

- "Form follows function" — declare the reader task first; the task
  constrains the form [C p. 34; K doc 13].
- "Whatever will be easiest for your audience to read" wins ties
  [K doc 10].
- "The most common chart types should dominate": bars, lines, dots,
  tables [S p. 80]. Novel forms carry a redundancy tax [C p. 83].
- Compute derived variables BEFORE choosing the form — the difference,
  ratio, or per-capita value often IS the story [C pp. 37–38, 108–109;
  S p. 17].
- State the claim in words on the chart; no neutral "X vs Y" titles
  [S pp. 56–57; K doc 13].

---

## A. Comparison across categories (no time)

| Form | Use when | Avoid when | Verdicts |
|---|---|---|---|
| **Horizontal bar** | default for categorical; long labels; many categories | — | K: "single go-to graph" [K doc 10]; order by value desc unless natural order |
| **Vertical bar (column)** | few categories, short labels | labels force diagonal text | rotate the chart, never the text [S p. 371; K doc 11] |
| **Dot plot** | long category lists; range/CI endpoints; cleaner than bars | audience unfamiliar (add redundancy) | best for mean+CI per category [S pp. 107–108] |
| **Lollipop** | slimmer bars; horizontal variant for long labels | — | add direct labels; can drop axis [S pp. 108–110] |
| **Dumbbell** | TWO values per category (before/after, group A/B) and the *gap* is the claim | >2 series | legend upper-left in series colors; can drop axis if labeled [S pp. 94–95] |
| **Grouped bar** | 2 (max 3) series × few categories | many series × many categories | ratio first bar 0.6–0.7 of cluster; order series by story [S p. 360; K doc 10] |
| **Slopegraph** | exactly two time points/conditions; change is the claim | many overlapping lines | direct labels both ends [S pp. 95–96; K docs 10, 17] |
| **Big number(s)** | 1–2 numbers ARE the claim | — | "communicating with just one or two numbers directly" [K doc 17; S pp. 326–328] |

Rules: zero baseline for all length encodings [S pp. 29–30; K doc 10];
bar width > gap but not so wide areas get compared [K doc 10]; the
segment/series that must be compared sits on the baseline
[S pp. 360–362; K doc 14].

## B. Change over time

| Form | Use when | Avoid when | Verdicts |
|---|---|---|---|
| **Line** | default; continuous data only | categories (line implies connection) | x-intervals must be uniform [K doc 10]; y-range within ~⅓–2× data range, justify deviation [S pp. 139–140] |
| **Small-multiple lines** | >4–5 series (spaghetti threshold) | — | identical scales across panels, ordered alphabetically/by value [S pp. 148–149; K doc 17] |
| **Highlight + gray** | ≤5 series, one is the story | exploratory mode | accent vs light gray [C pp. 25–26; S pp. 147–148] |
| **Interactive highlight** | 6–20 series, exploratory | static output | user picks from searchable menu [S p. 147] |
| **Connected scatter** | two variables co-evolve over time | audience can't follow the path | label years directly; Cairo's case for covariation [S pp. 145–147; C pp. 17–18] |
| **Slopegraph** | exactly two points | — | see A |
| **Step line** | rates that hold between changes | smooth phenomena | honest for policy-rate-style data |
| **Area/stream** | part-to-whole over time, pattern only | precise reading | streams have no baseline — never for values [S pp. 143–145] |

Missing data: visible gap or dashed segment, never silent interpolation
[S p. 152]. Line vs bars for two time points: slopegraph encodes the
change; paired bars make readers do the subtraction [K doc 17].

## C. Distribution

| Form | Use when | Verdicts |
|---|---|---|
| **Histogram** | default; raw counts | consider per-capita/percent for cross-group [S pp. 157–159] |
| **Density curve** | smooth shape; overlay 2–3 groups | max ~3 overlapping curves [S pp. 161–163] |
| **Strip / beeswarm** | every point visible; moderate n | strip = honest [T]; beeswarm for large n |
| **Box/violin** | summaries across many groups | box hides bimodality — pair with points or violin [S pp. 166–167] |
| **ECDF** | read percentiles directly | less intuitive; label percentiles |
| **Ridgeline** | distribution across many ordered groups | overlapping densities; joy division risk is aesthetic only |

## D. Relationship (x vs y)

| Form | Use when | Verdicts |
|---|---|---|
| **Scatter** | default; the relationship IS the claim | add trend line + CI; label outliers directly [S pp. 190–191] |
| **Bubble** | third variable by area, pattern only | NEVER for precise comparison [C pp. 44–48; S pp. 133, 195] |
| **Quadrant scatter** | two averages divide the field | shade/label quadrants; Cairo & K model visuals |
| **Paired maps/charts** | geographic x vs y | two side-by-side views force mental subtraction — plot the relationship directly instead [C pp. 110–117] |

Correlation trap: r = −0.67 invisible in a table, obvious in a scatter
[C pp. 110–117].

## E. Part-to-whole

| Form | Use when | Avoid when | Verdicts |
|---|---|---|---|
| **100% stacked bar** | composition across ≤5 categories; Likert data | comparing interior segments | dual baselines (left+right) for Likert [K docs 10, 17]; footnote absolute totals [K doc 14] |
| **Stacked bar (abs)** | totals + composition | interior comparison | only bottom segment comparable [S pp. 360–362] |
| **Treemap** | hierarchical part-to-whole, pattern only | precise comparison | area encoding — low accuracy tier |
| **Pie** | **never in this pipeline** | — | K: "evil" [K doc 10]; S tolerates with rules (start 12:00, largest-first, ≤5 slices, direct labels, no legend, sum-100% note) [S pp. 235–237]; C tolerates when angle is secondary [C pp. 78–79]. **Platform verdict: bars. Always.** |
| **Donut** | **never** | — | K: "Don't use donut charts" [K doc 10]; S: center must stay empty, angle not the main visual [S p. 234]. **Platform verdict: replace with 100% bar or big number.** |
| **Waffle** | rough share-of-100 | precise reading | square grid; S pp. 236–237 |

## F. Geospatial

See [[07-maps]] for the full doctrine. Summary: normalize before
mapping; choropleth = binned diverging/sequential scale; geographic
size ≠ importance (cartogram/tile grid when it distorts); symbols
transparent + outlined; "should this be a map?" first [S pp. 215–217].

## G. Single number / flow / process

- **Big number**: 1–2 values, giant type + sparse context [K doc 17;
  S pp. 326–328].
- **Sankey**: flows between states; pattern only, not precise
  quantities [S pp. 238–240].
- **Waterfall**: start + deltas → end; invisible-base stacked-bar hack
  [K doc 10].
- **Flowchart/timeline**: process and sequence; minimize line crossings
  [S pp. 246–248].

## H. Uncertainty (a first-class claim shape)

- **CI whiskers / error bars are BANNED (user directive 2026-08).** Point
  estimates only; interval bounds live in the fallback data table so
  statistical claims stay verifiable without drawing them.
- **Gradient / interval strip** (1–2 values): uncertainty directly
  visible [S p. 201; NYT 2016 election]. *(Also banned by the same
  directive — no interval marks of any kind.)*
- **Fan chart**: forecast cones; annotate "projection" on the cone
  [S pp. 202–203]. *(Banned — no interval marks.)*
- **Line + CI band**: mean ± SE [S pp. 203–204]. *(Banned — no interval
  marks.)*
- Rule: uncertainty is *reported in the data table*, not drawn — label
  what the interval IS (95% CI vs SE) in the table [S ch. 6].

## Cross-book conflict adjudication

| Topic | K | S | C | Platform verdict |
|---|---|---|---|---|
| Pie | evil | tolerable w/ strict rules | tolerable if angle secondary | **bars always** |
| Donut | never | center empty, non-angle | — | **never; big number or 100% bar** |
| Chartjunk | remove (via Tufte) | balance | evidence: harmless, aids recall [C pp. 66–67] | **minimal by default; delight allowed only when zero accuracy cost** |
| Bubbles | — | area rules + label | "plague" | pattern-only, transparent, labeled |
| Table vs chart | tables read, graphs seen | 10 table rules | honest table > dishonest bubble | **table when precision, chart when pattern** |
