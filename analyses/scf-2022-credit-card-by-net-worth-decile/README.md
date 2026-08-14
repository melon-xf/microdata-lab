# SCF 2022 credit-card balances by net-worth decile

## Question

What is the average credit-card balance among all U.S. families in each net-worth decile in the 2022 Survey of Consumer Finances?

## Estimand

Weighted mean of `CCBAL`, including families with zero balances, within ten approximately equal-weight groups ordered by `NETWORTH`.

## Survey treatment

- Record unit: SCF primary economic unit (“family”).
- Five implicates are estimated separately and combined.
- Weighted deciles are recomputed within each implicate.
- Ties are resolved deterministically by family identifier after ordering by net worth.
- Sampling variance uses the first implicate and all 999 bootstrap replicate weights multiplied by their corresponding multiplicity factors.
- Replicate deciles are recomputed under each replicate weight.
- Total variance is `sampling variance + (6/5 × imputation variance)`, following the 2022 SCF codebook’s `MEANIT` method.
- Confidence intervals use the normal 1.96 critical value.

## Important interpretation

`CCBAL` measures revolving credit-card debt carried by the family. It is not total card spending. Families that use cards but pay the balance in full appear as zero. Buy-now-pay-later balances are separate in the 2022 SCF and are not included here.

## Outputs

- `data.csv`: estimates and diagnostics used by both renderers.
- `question.md`: estimand, universe, variables, design, assumptions, and release identity.
- `diagnostics.json`: release, design, uncertainty, missingness, and benchmark checks.
- `chart.yaml`: shared semantic presentation contract.
- `figure.png`: static publication graphic.
- `interactive.html`: standalone responsive chart with tooltips and a data table.
