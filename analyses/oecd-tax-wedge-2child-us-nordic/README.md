# OECD Tax Wedge: Single Adult with Two Children, US vs Nordic (2025)

Replicates a published figure 2
(`nordic_s_c2_average_wedge-1.png`).

## Finding

For a single adult with two children, the US average tax wedge (21.30% at
the average wage) is below all four Nordic countries at every wage level
50–250% of the average wage, once child cash benefits (EITC/ACTC/CTC in
the US; Nordic child benefits) are netted per the OECD definition.

## Data

- OECD Tax Wages decomposition, measure `AV_TW`, household type `S_C2`
  (single adult, two children), 2025.
- Release: `oecd_tax_wages-2025`.

## Method

OECD average tax wedge net of child cash benefits. No sampling variance —
official macrodata.

## Files

- `estimate.py`, `data.csv`, `diagnostics.json`, `chart.yaml`,
  `figure.png`, `interactive.html`
