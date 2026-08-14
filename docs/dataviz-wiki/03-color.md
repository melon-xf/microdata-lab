# 03 — Color

Sources: Schwabish ch. 3 [S], Cairo ch. 6–7 [C], Knaflic ch. 4 [K].

## The restraint consensus (all three books agree)

One accent + neutrals. Everything else is noise.

- S: "subtle color palette… grey, dark blue, light blue, orange"
  (Urban Institute) [S p. 68]; base gray not black so accent pops
  [K doc 12].
- C: "Pure colors are uncommon in nature, so limit them to highlight
  whatever is important… use subdued hues—grays, light blues, and
  greens—for everything else… prioritize beforehand" [C p. 95].
  "Stick to just two or three colors and play with their shades"
  [C p. 152].
- K: shades of grey + single bold color; "Never let your tool make this
  important decision for you!" [K doc 12].
- Highlight ≤10% of the content or emphasis dilutes to nothing
  [K doc 13, Lidwell].

## The five scheme types [S pp. 63–68]

1. **Binary**: highlight one group (accent + gray). Use for "this one
   thing matters."
2. **Sequential**: ordered magnitude; single-hue lightness ramp; best
   for low→high with a natural zero. Neutral center when 0 matters
   (0–100% scales: white at 0).
3. **Diverging**: meaningful midpoint (0, parity, average); two hues
   meeting at a light center. Red↔blue reads negative↔positive in US
   contexts; red↔green is forbidden (CVD).
4. **Categorical**: ≤4–5 hues max (working memory) [C p. 125]; beyond
   that, facet or use position.
5. **Highlighting**: one series in accent, rest in light gray — the
   default for >2 series in explanatory mode.

## Rules

- **Consistency = semantics**: a color change signals a meaning change;
  the audience learns your palette once and assumes it everywhere
  [K doc 12; S pp. 68–69]. Subject→color mapping is fixed across ALL
  charts in a project.
- **CVD**: ~8% of men, most common red-green. Never encode meaning in
  red↔green alone; add a secondary cue (bold, saturation, +/−)
  [K doc 12; S p. 68]. K's safe convention: blue = positive,
  orange = negative.
- **Rainbow = lint error**: "different colors in a rainbow palette
  imply categorical differences that do not exist" [S p. 68]; rainbow
  table = "everything different = nothing stands out" [K doc 12].
- **Dark backgrounds**: normally avoid (heavy, pulls eyes from data);
  if forced, invert the contrast logic — on black, what stands out is
  furthest from black (white); yellow forbidden on white grabs on
  black [K doc 17].
- **Culture**: red = danger/deficit/Republican in US; green =
  positive/envy; check connotations for the audience [S pp. 64–65;
  C p. 152].
- **Print/B&W survival**: palette must degrade gracefully to grayscale
  [K doc 12].
- Text legibility: no large colored text blocks; sans-serif for data
  labels; contrast ≥ WCAG AA [S pp. 66–67, 363].

## Choropleth specifics

Continuous or 3–9 binned steps; diverging only with a meaningful
center; light = low; never rainbow [S pp. 222–223]. (Full map doctrine:
[[07-maps]].)

## Renderer checklist

- [ ] Scheme type declared in config (binary/sequential/diverging/
      categorical/highlight)
- [ ] Categorical palette refuses >5 hues
- [ ] Red-green pairings rejected at validation
- [ ] Accent + gray default; saturation reserved for the claim
- [ ] Subject-color mapping lives in ONE shared config, used by every
      chart
- [ ] Palette survives grayscale conversion test
