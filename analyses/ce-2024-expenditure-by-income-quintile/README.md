# Household Spending by Income Quintile, 2024

## Methods

Analysis of the 2024 Consumer Expenditure Survey (CE) Interview Public Use File. Consumer units were assigned to five weighted income quintiles using `FINCBTAX` (total income before taxes). Weighted mean quarterly expenditure (`TOTEXPPQ`) was computed within each quintile using `FINLWT21`. Standard errors were computed from 44 BRR replicate weights; 95% confidence intervals use the normal approximation.

## Results

| Quintile | Mean income | Mean expenditure | 95% CI | Sample n |
|---|---|---|---|---|
| Q1 (lowest 20%) | $5,726 | $8,145.61 | [$7,450, $8,841] | 4,449 |
| Q2 | $31,933 | $8,003.02 | [$7,621, $8,386] | 4,713 |
| Q3 | $62,036 | $10,827.36 | [$10,447, $11,208] | 4,607 |
| Q4 | $107,537 | $14,655.08 | [$14,247, $15,063] | 4,593 |
| Q5 (highest 20%) | $247,139 | $23,824.95 | [$22,921, $24,729] | 4,814 |

Spending rises with income but less than proportionally. The highest-income quintile earns 43× more than the lowest but spends only 2.9× more, reflecting higher savings rates among high earners and constrained spending among low earners.

## Limitations

- Quarterly expenditure (`TOTEXPPQ`) does not capture all annual spending; the CE Interview covers major purchases but misses small, frequent items covered by the Diary survey.
- Income is annualized; expenditure is quarterly. Direct ratio comparison requires caution.
- BRR-based SEs reflect sampling variance only, not imputation or coverage error.

## Source

BLS, Consumer Expenditure Survey 2024 Interview Public Use File.
Release ID: `ce-2024-69ef4ff25c24`.