# Source selection: severe housing-cost burden by rental assistance

## Decision

Use the 2023 American Housing Survey (AHS) national household file. It directly identifies respondent-reported public housing, vouchers, other government rental assistance, and no assistance; provides monthly total housing costs and household income; and ships 160 replicate weights for publishable uncertainty.

## Comparison

| Candidate | Concept and variables | Record unit / universe | Geography / year | Design | Local status | Decision |
|---|---|---|---|---|---|---|
| **AHS 2023** | `RENTSUB` rental-assistance type; `TOTHCAMT` total monthly housing costs; `HINCP` past-12-month household income; `PERPOVLVL` income as percent of poverty | Housing unit; occupied renter households | U.S. national, 2023 | `WEIGHT`; 160 `REPWEIGHT` variables; variance factor 4/160 | Validated release `ahs-2023-cd440e383936`; official codebook and variance guide retained | **Selected** |
| SIPP 2025 | Monthly rent subsidy and voucher receipt, income and poverty | Person-month / household-month; longitudinal panel | U.S. national, 2025 | Person/household weights, variance strata and half-sample design | Validated release exists | Strong for transitions and duration, but more complicated than needed for a cross-sectional burden comparison |
| ACS PUMS 2024 | Gross rent, household income, tenure | Person/housing unit | U.S., states, PUMAs, 2024 | Person/housing weights and replicate weights | Validated licensed-IPUMS release exists | Cannot cleanly distinguish public housing, vouchers, and unassisted renters |

## Comparability and limitations

- AHS `RENTSUB` is a respondent-reported derived classification. Code `1` is public housing; codes `2` and `3` are portable and non-portable vouchers; codes `4` and `5` are other government assistance; code `8` is no rental subsidy or reduction.
- `TOTHCAMT` includes rent, utilities, and other housing costs. It is not rent alone.
- `PERPOVLVL` is rounded. Bands use the released rounded percent of poverty.
- The analysis is descriptive. Assistance recipients and unassisted renters differ in need, geography, household composition, housing supply, and selection into programs. The estimates do not identify a causal treatment effect.
- Households with nonpositive income are excluded because a housing-cost-to-income ratio is undefined or not interpretable. This exclusion is material at the very bottom and is reported in diagnostics.
