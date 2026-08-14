# US vs Nordic average labor tax wedge with family ESI premiums (2025)

## Claim

For a single adult with two children at the average wage, counting the
average family ESI premium as a tax brings the US average labor tax wedge
to roughly the Nordic level — the US is no longer the lowest-tax country.

## Source to replicate

Bruenig, Matt. "The US and the Nordics have similar labor taxes." People's
Policy Project, June 5, 2026 — figure 4 ("nordic_s_c2_average_wedge_health-1.png").

## Estimand

Average tax wedge plus family ESI premium as a percent of labor cost, by
wage level (AW50–AW250), single adult with two children (S_C2), 2025.

## Data

- OECD Tax Wages decomposition (DSD_TAX_WAGES_DECOMP), AV_TW and GWE by
  wage level for S_C2.
- KFF 2025 Employer Health Benefits Survey: average annual family premium
  $26,993 (worker share $6,850, employer share $20,143).

## Method

Same normalization as the single-adult ESI figure, using the family
premium. Bruenig's figure 4 shows the US line moving from lowest to
near the Nordic middle.

## Benchmark

USA, S_C2, AW100, 2025: wedge + family ESI ≈ 33% (Bruenig figure 4).

## Outputs

figure.png + interactive.html, multi-series line chart with US adjusted.
