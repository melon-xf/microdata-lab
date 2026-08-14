# OECD Tax Wedge incl. Family ESI Premium, US vs Nordic (2025)

Reproduces figure 4 from Matt Bruenig's "The US and the Nordics have similar
labor taxes" (People's Policy Project, June 5, 2026).

## Finding

For a single adult with two children, adding the average family ESI
premium to the US tax wedge pushes the US above the Nordic average at the
average wage — the family-healthcare cost normalization fully closes (and
reverses) the US "low tax" gap.

## Data

- OECD Tax Wages decomposition, measures `AV_TW` and `LC`, household type
  `S_C2`, 2025. Release: `oecd_tax_wages-2025`.
- KFF 2025 Employer Health Benefits Survey: family premium $26,993
  (worker $6,850, employer $20,143).

## Method

Same normalization as the single-ESI figure, using the average family
premium applied to the two-children household.

## Files

- `estimate.py`, `data.csv`, `diagnostics.json`, `chart.yaml`,
  `figure.png`, `interactive.html`
