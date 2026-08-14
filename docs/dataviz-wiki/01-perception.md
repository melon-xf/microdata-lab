# 01 — Perception & Preattentive Processing

How readers actually see charts. Sources: Schwabish ch. 1 [S],
Cairo ch. 5–7 [C], Knaflic ch. 4 [K], Tufte [T].

## The encoding hierarchy (the load-bearing ranking)

Cleveland & McGill (1984), confirmed by Heer & Bostock, cited by all
three modern authors [S pp. 25–26; C pp. 106–107; K doc 12]:

1. Position on a **common scale**
2. Position on **nonaligned scales**
3. **Length**, direction, angle
4. **Area**
5. Volume, curvature
6. Shading, color saturation

> **The more accurate the judgment the reader must make, the higher on
> this scale the encoding must sit** [C p. 108].

Direct consequences:

- Bars (length + common baseline) beat dots beat slopes beat areas beat
  hues for any precise comparison.
- "A bar chart is always superior to a bubble chart or a heat map if
  the goal of the graphic is to facilitate precise comparisons"
  [C p. 108].
- Readers compare bubble **diameters**, not areas — area encodings
  systematically *underestimate* differences [C p. 46; S p. 133].
- Hue is a *categorical* differentiator, not quantitative: "which is
  greater — red or blue?" is not meaningful [K doc 12]. Quantity via
  color = saturation/intensity ramp only.
- Low-ranked encodings (shading, area) are acceptable when the goal is
  big-picture pattern, not precise values [C pp. 109–110] — this is the
  choropleth's license to exist.

## Preattentive attributes

Processed in iconic memory in <500 ms, before conscious attention
[S pp. 37–40; K doc 12; C pp. 100–102]: color/hue, intensity, size,
length, orientation, position, enclosure, shape, motion.

- Use them to make the important values effortless to find — "enable
  our audience to see what we want them to see before they even know
  they're seeing it" [K doc 12].
- The brain detects **shade variation faster than shape difference**
  [C p. 101] — prefer color-coding over multiplying symbol shapes.
- **Double-edged**: highlighting one thing actively suppresses the rest
  → never use preattentive emphasis in exploratory/neutral renders
  [K doc 12].
- Motion and bright color pull attention even peripherally: never run
  animation next to text the reader must read [C pp. 94–95].

## Memory limits

- Short-term visual memory: **~4 chunks** [K doc 12, citing Cowan].
  10 series × 10 colors + a legend = guaranteed overload → direct-label
  series to form larger chunks.
- Cairo's rendering rule from Miller: **no more than 4–5 hues or
  pictogram types** identifying phenomena on one chart [C p. 125].
- Long-term encoding is strongest when visual + verbal channels combine
  — label in words, don't rely on marks alone [K doc 12].

## Gestalt principles → design operations

[S pp. 34–37; C pp. 102–105; K doc 11]

| Principle | Perceptual fact | Design operation |
|---|---|---|
| Proximity | close = grouped | group by spacing, not boxes |
| Similarity | same color/shape = same group | color can replace borders |
| Enclosure | boxed = grouped | light shading only; avoid overuse |
| Closure | eyes fill gaps | chart borders/backgrounds unnecessary — remove them |
| Continuity | eyes seek smooth paths | y-axis line removable; white space aligns |
| Connection | lines overrule color/shape | line charts bind series; connection is the strongest grouping after enclosure |

**Hazard**: closure means readers mentally close gaps — a line chart
with missing data reads as continuous. Signal missing data with a
visible gap or dashed segment [S p. 152; S p. 36].

## Known perceptual illusions that corrupt charts

- **Line-width illusion**: readers measure closest-point distance
  between two curves, not vertical distance → two converging lines
  overstate convergence; plot the difference directly [S pp. 149–150].
- **Within-the-bar bias**: points inside a bar are judged more likely
  than points outside — relevant to error bars on bars [S p. 201].
- **3D projection**: Excel-style 3D reads a value of 1.0 as 0.8; depth
  adds side/floor planes with no data [K doc 10; S pp. 43–44].
- **Area growth**: Brinton 1914 — scaling icon height 2× grows area 4×;
  never scale pictogram icons to value [S pp. 119–120].
- **Light-from-above**: shading reads as concave/convex — avoid
  gradient fills that imply depth [C pp. 117–118].

## Foveal reality

Only ~2° of the visual field has full acuity; readers scan in saccades
(2–3/sec), roughly z-pattern from top-left for Western readers
[C pp. 92–93; K doc 11]. Consequences: the "how to read this" elements
(title, axis titles, key) belong upper-left; the most important content
gets the top of the page [K doc 11–12].

## The 3–8 second window

"We have about 3–8 seconds with our audience" [K doc 12]. The gist
must be preattentively available inside that window; everything else is
progressive disclosure.

## Renderer checklist

- [ ] Encodings chosen from the highest tier the claim requires
- [ ] ≤4–5 hue categories; quantity never encoded as hue
- [ ] Emphasis marks only in explanatory mode
- [ ] Missing data = visible gap/dash, never silent interpolation
- [ ] No 3D, no gradients implying depth, no icon area scaling
- [ ] Title/key/axis titles in the upper-left reading zone
