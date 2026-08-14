# Question and estimand

## Question

What is the average revolving credit-card balance among all U.S. families in each family net-worth decile in the 2022 Survey of Consumer Finances?

## Estimand

For each weighted decile of concurrent family net worth, the design-weighted mean of `CCBAL`, including families with zero revolving balances.

## Record unit and universe

- Record unit: SCF family/primary economic unit.
- Universe: all families represented by the 2022 SCF public-use file.
- Denominator: all weighted families assigned to each decile.
- Exclusions: none beyond invalid/nonpositive analysis weights; the validated release contains none.

## Variables and definitions

- `NETWORTH`: summary-extract family net worth. Definition comes from the Federal Reserve's `bulletin.macro.txt`, retained in the validated release documentation sidecar.
- `CCBAL`: revolving credit-card balance; set to zero for families who pay cards in full or have no balance, per the official summary-variable definition.
- `WGT`: public summary-extract analysis weight. The extract divides population weight across five implicates, so population counts are multiplied by five; constant scaling cancels from means and weighted decile assignment.
- `YY1`, `Y1`: family and implicate identifiers.
- `wt1b1`–`wt1b999`, `mm1`–`mm999`: supplied bootstrap weights and multiplicity factors.

## Design and uncertainty

1. Construct ten approximately equal-weight groups independently within each implicate using cumulative-weight midpoints after stable ordering by `NETWORTH` and family ID.
2. This stable ordering splits exact net-worth ties deterministically; ties are not broken using the outcome.
3. Average the five implicate-specific estimates.
4. Recompute deciles and means for each of the 999 supplied bootstrap replicates using `wt1bN * mmN` on implicate 1.
5. Sampling variance is the sample variance across replicate estimates. Multiple-imputation variance is the sample variance across the five implicate estimates. Total variance is sampling variance plus `6/5` times imputation variance.
6. Confidence intervals use the normal approximation: estimate ± 1.96 standard errors.

## Release

- Release ID: `scf-2022-7b35624679b4`
- Release SHA-256 identity: `7b35624679b477113adf7387f6c7c1f4cb46603815dc3eb0d1515de9e441401a`
- Official landing page: <https://www.federalreserve.gov/econres/scfindex.htm>
