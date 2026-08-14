# OECD Tax Wedge incl. Single ESI Premium, US vs Nordic (2025)

Reproduces figure 3 from Matt Bruenig's "The US and the Nordics have similar
labor taxes" (People's Policy Project, June 5, 2026).

## Finding

Adding the average single employer-sponsored health insurance (ESI)
premium to the US tax wedge, using Bruenig's normalization, brings the
US average-wage worker to roughly the Nordic average tax level — the US is
no longer the lowest-tax country.

## Data

- OECD Tax Wages decomposition, measures `AV_TW` and `LC` (labor cost),
  household type `S_C0`, 2025. Release: `oecd_tax_wages-2025`.
- KFF 2025 Employer Health Benefits Survey: single premium $9,325
  (worker $1,440, employer $7,885).

## Method

Following Bruenig's published normalization, the employer share counts toward labor
cost; both employer and employee shares count toward the tax. Applied to
US values across the wage grid; Nordic wedges unchanged (public health
insurance already in their social security contributions).

## Files

- `estimate.py`, `data.csv`, `diagnostics.json`, `chart.yaml`,
  `figure.png`, `interactive.html`
