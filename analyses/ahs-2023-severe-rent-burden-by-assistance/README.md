# Severe housing-cost burden by rental assistance, AHS 2023

## Finding

Among occupied renter households with positive income at or below 200% of the poverty threshold, severe housing-cost burden is consistently lower with public housing or a voucher than with no rental assistance.

| Income as % of poverty | Public housing | Voucher | No assistance |
|---|---:|---:|---:|
| ≤50% | 89.0% | 86.8% | 98.2% |
| 51–100% | 26.9% | 35.9% | 81.5% |
| 101–150% | 23.0% | 16.9% | 53.4% |
| 151–200% | 13.5% | 18.5% | 36.0% |

The bottom band is the warning: when household income is no more than half the poverty threshold, assistance does not make housing affordable for most renters. In the next three bands, however, the descriptive gap is large.

## Methods

- 2023 AHS National household PUF, release `ahs-2023-cd440e383936`.
- Occupied renter households (`INTSTATUS=1`, `TENURE=2`) with positive household income, released poverty level ≤200%, nonnegative total monthly housing cost, and a classified rental-assistance value.
- Severe burden = annualized `TOTHCAMT` greater than 50% of `HINCP`.
- Assistance comes from respondent-reported `RENTSUB`: public housing (`1`), vouchers (`2`/`3`), and no subsidy/reduction (`8`). Other government assistance (`4`/`5`) is estimated in diagnostics but omitted from the publication chart.
- Point estimates use `WEIGHT`; uncertainty uses all 160 AHS replicate weights and the official `4/160` variance factor.
- The official occupied-unit benchmark reproduces: 133,230.777 thousand units and 90% MOE 381.054 thousand.

## Interpretation

This is evidence that assistance recipients experience different housing-cost burdens, not proof that program assignment caused the gap. Recipient need, geography, household composition, local rents, housing quality, and program selection all differ. `RENTSUB` is respondent-reported; `TOTHCAMT` includes utilities and other housing costs, not rent alone.

## Files

- `source-selection.md` — why AHS was chosen over SIPP and ACS PUMS.
- `question.md` — estimand, universe, variables, design, assumptions, and release.
- `estimate.py` — executable calculation and benchmark.
- `data.csv` — exact public-housing versus no-assistance values supplied to both renderers.
- `all-groups.csv` — public housing, voucher, and no-assistance values with standard errors and intervals.
- `diagnostics.json` — row counts, weighted households, design, exclusions, benchmark, and all assistance-group estimates.
- `chart.yaml`, `figure.png`, `interactive.html` — shared chart contract and render artifacts.
