# US vs Nordic average labor tax wedge, single adults (2025)

## Claim

At every wage level between 50% and 250% of the average wage, the United
States has a lower average labor tax wedge than Denmark, Finland, Norway,
and Sweden for a single adult with no children.

## Source to replicate

Bruenig, Matt. "The US and the Nordics have similar labor taxes." People's
Policy Project, June 5, 2026 — figure 1 ("nordic_single_average_wedge-1.png").

## Estimand

Average tax wedge (AV_TW): total taxes + employee and employer social
security contributions as a share of total labor cost, by wage level as a
percent of the average wage (AW50–AW250), for household type single adult
with no children (S_C0), 2025.

## Record unit and universe

Country × wage-level × household-type observation. Universe: OECD Tax
Wages decomposition, 2025, five countries (USA, DNK, FIN, NOR, SWE).

## Data

OECD SDMX 2.1 REST, flow DSD_TAX_WAGES_DECOMP@DF_TW_DECOMP, measure
AV_TW, household type S_C0, income principal AW50–AW250, time 2025.

## Denominator, exclusions, missing

Tax wedge is tax/(gross wage + employer social security contributions).
Excludes cash benefits (handled in the two-child variant). No missing
observations in the extracted wage grid.

## Weight and design

Macrodata; no survey weights, no replicate weights, no sampling variance.

## Uncertainty

None — official point estimates. No confidence intervals.

## Benchmark

USA, S_C0, AW100, 2025: AV_TW = 29.98% (from OECD release).

## Outputs

figure.png + interactive.html, multi-series line chart.
