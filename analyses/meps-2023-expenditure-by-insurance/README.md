# Mean Total Health Expenditure by Insurance Coverage, 2023

## Methods

Analysis of the 2023 Medical Expenditure Panel Survey (MEPS) HC-251 full-year consolidated data file. The weighted mean total health care expenditure (`TOTEXP23`) was computed for each insurance coverage category (`INSCOV23`) using full-year person weights (`PERWT23F`). Standard errors were approximated using Taylor linearization; confidence intervals use the normal approximation at the 95% level.

## Results

| Insurance type | Mean expenditure | 95% CI | Weighted population |
|---|---|---|---|
| Uninsured | $1,061.70 | [$807, $1,316] | ~4.9M |
| Any private | $7,600.08 | [$7,177, $8,023] | ~196M |
| Public only | $8,635.44 | [$8,091, $9,180] | ~134M |

The uninsured spend roughly one-eighth of what the publicly insured spend and one-seventh of what the privately insured spend per person per year.

## Limitations

- Standard errors use an analytic approximation (Taylor linearization), not the official BRR replicate-weight design. Official SEs may differ.
- `TOTEXP23` includes all direct medical expenditures but excludes insurance premiums.
- Expenditure values are nominal 2023 USD (not inflation-adjusted).
- Insurance coverage is classified as of the person's 2023 coverage; transitions during the year are not modeled.

## Source

AHRQ, Medical Expenditure Panel Survey HC-251 (2023). Public domain (17 USC §105).
Release ID: `meps-2023-71d2d7091b8d`.