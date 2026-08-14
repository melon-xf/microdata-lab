# Question and estimand

## Question

Among occupied U.S. renter households with positive income at or below 200% of the poverty threshold, how does the share spending more than half of household income on total housing costs vary by poverty band and respondent-reported rental-assistance type in 2023?

## Estimand

For each released poverty band and rental-assistance group, the AHS design-weighted share for which:

`12 × TOTHCAMT / HINCP > 0.50`

The publication chart compares public housing with no assistance so the connector length directly encodes the gap. Voucher estimates are retained in `all-groups.csv`; other government assistance is retained in diagnostics.

## Record unit and universe

- Record unit: AHS occupied housing unit / household.
- Universe: `INTSTATUS = 1`, `TENURE = 2`, positive `HINCP`, `PERPOVLVL` from 2 through 200, nonnegative `TOTHCAMT`, positive `WEIGHT`, and a classified `RENTSUB` value.
- Denominator: weighted renter households within each poverty-band × assistance cell.
- Poverty bands: ≤50%, 51–100%, 101–150%, and 151–200% of the official poverty threshold.
- Exclusions: non-renters; usual-residence-elsewhere and vacant units; nonpositive or missing household income; missing/not-applicable housing costs, weights, poverty level, or rental-assistance classification.

## Variables and definitions

Definitions are from the retained official AHS codebook (`variables.json` + `details.json`) for 2023 National:

- `RENTSUB`: respondent-reported derived rental subsidy/reduction type. `1` = public housing; `2`/`3` = portable/non-portable voucher; `4`/`5` = other government assistance or annual recertification; `8` = no rental subsidy or reduction.
- `TOTHCAMT`: monthly total housing costs; sum of rent and applicable utilities/other housing costs.
- `HINCP`: household income during the past 12 months, summed over household members age 16+.
- `PERPOVLVL`: rounded household income as a percent of the poverty threshold.
- `TENURE`: owner or renter status.
- `INTSTATUS`: interview status.
- `WEIGHT`: final national AHS weight.
- `REPWEIGHT1`–`REPWEIGHT160`: official replicate weights.

Structural zero, missing, and out-of-universe codes are not treated as observed zeros. Literal quote marks retained in normalized AHS character codes are stripped before classification.

## Design and uncertainty

- Point estimates use `WEIGHT`.
- Each cell estimate is recomputed with all 160 replicate weights.
- Replicate variance follows the official AHS rule: `(4/160) × Σ(replicate − full-sample estimate)²`, equivalent to variance factor `0.025`.
- Standard errors and 95% normal-approximation confidence intervals are retained in `data.csv` and the accessible table. Per project policy, the chart shows point estimates only and never draws CI whiskers.

## Benchmark

Before accepting the analysis, reproduce the official 2023 AHS occupied-unit benchmark: 133,231 thousand occupied units with 90% margin of error 381 thousand. The validated release reports 133,230.777 thousand and MOE90 381.054 thousand.

## Release

- Release ID: `ahs-2023-cd440e383936`
- Release SHA-256 identity: `cd440e383936eaaa0435fc63be15caae2e95b6f29aadf0a88d6e147dd3ebfee6`
- Official landing page: <https://www.census.gov/programs-surveys/ahs/data/2023/ahs-2023-public-use-file--puf-/ahs-2023-national-public-use-file--puf-.html>
