# OECD Tax Wedge: Single Adults, US vs Nordic (2025)

Replicates a published figure 1
(`nordic_single_average_wedge-1.png`) from a June 2026 labor-tax article.

## Finding

At every wage level from 50% to 250% of the average wage, the US average
labor tax wedge (29.98% at the average wage) sits below all four Nordic
countries (Denmark 35.8%, Finland 42.5%, Norway 36.4%, Sweden 41.1%).

## Data

- OECD Tax Wages decomposition (`DSD_TAX_WAGES_DECOMP`), measure `AV_TW`
  (average tax wedge), household type `S_C0` (single, no children), 2025.
- Release: `oecd_tax_wages-2025` (SDMX 2.1 REST).

## Method

Average tax wedge = (employee SSC + employer SSC + income tax) / total
labor cost, including cash benefits per the OECD definition. No sampling
variance — official macrodata.

## Files

- `estimate.py` — reproducible computation
- `data.csv` — chart data (wage_pct, country, avg_tax_wedge)
- `diagnostics.json` — benchmark (USA@100% = 29.98) and row counts
- `chart.yaml` — chart spec (multi-series line)
- `figure.png` / `interactive.html` — static and interactive outputs
