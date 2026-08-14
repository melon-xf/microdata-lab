# US vs Nordic average labor tax wedge, single adult with two children (2025)

## Claim

For a single adult with two children, the United States has a lower average
labor tax wedge than Denmark, Finland, Norway, and Sweden at most wage
levels between 50% and 250% of the average wage, but the gap narrows at
lower wage levels where US cash benefits (EITC/CTC) reduce the wedge.

## Source to replicate

Bruenig, Matt. "The US and the Nordics have similar labor taxes." People's
Policy Project, June 5, 2026 — figure 2 ("nordic_s_c2_average_wedge-1.png").

## Estimand

Average tax wedge (AV_TW) net of cash benefits, by wage level (AW50–AW250),
for a single adult with two children (S_C2), 2025. The OECD AV_TW already
nets out cash benefits for household types with children (EITC/ACTC/CTC in
the US; Nordic child benefits).

## Record unit and universe

Country × wage-level × household-type observation. Universe: OECD Tax
Wages decomposition, 2025, five countries (USA, DNK, FIN, NOR, SWE),
household type S_C2.

## Data

OECD SDMX 2.1 REST, flow DSD_TAX_WAGES_DECOMP@DF_TW_DECOMP, measure
AV_TW, household type S_C2, income principal AW50–AW250, time 2025.

## Denominator, exclusions, missing

Same wedge definition as the single-adult figure. Cash benefits for
children are included in the wedge calculation (they reduce it), matching
the article's first two graphs.

## Weight and design

Macrodata; no survey weights, no replicate weights, no sampling variance.

## Uncertainty

None — official point estimates.

## Benchmark

USA, S_C2, AW100, 2025: AV_TW = 21.30% (from OECD release).

## Outputs

figure.png + interactive.html, multi-series line chart.
