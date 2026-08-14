# US vs Nordic average labor tax wedge with ESI premiums (2025)

## Claim

Once employer-sponsored health insurance (ESI) premiums are counted as
taxes — matching how Nordic public health insurance contributions are
treated — the US average labor tax wedge for a single adult at the average
wage is comparable to (or above) the Nordic countries.

## Source to replicate

Bruenig, Matt. "The US and the Nordics have similar labor taxes." People's
Policy Project, June 5, 2026 — figure 3 ("nordic_single_average_wedge_health-1.png").

## Estimand

Average tax wedge plus ESI premium as a percent of labor cost, by wage
level (AW50–AW250), single adult with no children (S_C0), 2025.

The normalization adds the average US single ESI premium to both the tax
numerator and the labor cost denominator, then recomputes the wedge. The
employer share of the premium is counted as labor cost; the employee share
is counted as additional tax, following the article's stated method.

## Data

- OECD Tax Wages decomposition (DSD_TAX_WAGES_DECOMP), AV_TW and GWE
  (gross wage earnings) by wage level.
- KFF 2025 Employer Health Benefits Survey: average annual single premium
  $9,325 (worker share $1,440, employer share $7,885).

## Method

For each US wage level, recompute wedge' = (AV_TW × labor_cost + premium) /
(labor_cost + premium), where labor_cost at wage level w is derived from
GWE and the employer social security contribution. Bruenig's figure 3
applies the normalization at the average wage; this analysis extends it
across the wage grid.

## Benchmark

USA, S_C0, AW100, 2025: wedge + ESI ≈ 36% (Bruenig figure 3 shows the US
line crossing above the Nordic countries near the average wage).

## Outputs

figure.png + interactive.html, multi-series line chart with US adjusted.
