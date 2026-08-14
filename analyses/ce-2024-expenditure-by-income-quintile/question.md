# Question and estimand

## Question

How does household spending vary across income quintiles in the 2024 Consumer Expenditure Survey?

## Estimand

For each weighted income quintile of `FINCBTAX` (total family income before taxes), the weighted mean of `TOTEXPPQ` (total quarterly expenditure), using `FINLWT21` as the family weight and 44 BRR replicate weights for variance estimation.

## Record unit and universe

- Record unit: CE consumer unit (family/household).
- Universe: U.S. consumer units in the 2024 CE Interview Survey.
- Denominator: all weighted consumer units in each income quintile.
- Exclusions: none beyond invalid/nonpositive weights.

## Variables and definitions

- `FINCBTAX`: Total family income before taxes, annualized.
- `TOTEXPPQ`: Total expenditure, population-variant quarterly measure. Includes all goods and services purchased directly.
- `FINLWT21`: CE Interview Survey family weight.
- `WTREP01`–`WTREP44`: 44 BRR replicate weights.

## Design and uncertainty

1. Assign weighted income quintiles using cumulative-weight midpoints after stable ordering by `FINCBTAX`.
2. Compute weighted mean expenditure within each quintile.
3. Sampling variance from 44 BRR replicate weights: $SE = \sqrt{\frac{1}{44}\sum_{r=1}^{44}(\hat{\theta}_r - \hat{\theta})^2}$.
4. 95% CI: estimate ± 1.96 × SE.

## Release

- Release ID: `ce-2024-69ef4ff25c24`
- Official source: BLS CE 2024 Interview Public Use File