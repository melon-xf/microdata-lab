# Question and estimand

## Question

What is the mean total health care expenditure per person in the U.S. by insurance coverage type (any private, public only, uninsured) in 2023?

## Estimand

For each insurance coverage category (`INSCOV23`), the weighted mean of `TOTEXP23` (total direct health care expenditure), using `PERWT23F` as the analysis weight.

## Record unit and universe

- Record unit: MEPS person.
- Universe: U.S. civilian non-institutionalized population, 2023.
- Denominator: all weighted persons in each insurance category.
- Exclusions: none beyond invalid analysis weights.

## Variables and definitions

- `TOTEXP23`: Total direct health care expenditure for 2023, in nominal USD. Includes payments from all sources (insurance, out-of-pocket, other). Excludes insurance premiums.
- `INSCOV23`: Insurance coverage classification for 2023:
  - `1 ANY PRIVATE`: Any private insurance (employer-sponsored, directly purchased, or TRICARE).
  - `2 PUBLIC ONLY`: Public coverage only (Medicare, Medicaid, CHAMPUS/VA, other public).
  - `3 UNINSURED`: No health insurance coverage at any point in 2023.
- `PERWT23F`: Full-year person-level weight. Sums to the U.S. civilian non-institutionalized population.

## Design and uncertainty

MEPS uses a complex survey design with stratification and clustering. The main PUF (HC-251) does not include replicate weights; variance estimation requires separate BRR files. This analysis uses a Taylor linearization approximation for standard errors:

$$SE = \sqrt{\frac{\sum w_i^2 (x_i - \bar{x})^2}{(\sum w_i)^2}}$$

This is a conservative approximation; official MEPS variance estimation uses balanced repeated replication (BRR).

## Release

- Release ID: `meps-2023-71d2d7091b8d`
- Official landing page: `https://meps.ahrq.gov/mepsweb/data_stats/download_data_files_detail.jsp?cboPufNumber=HC-251`
- AHRQ public domain (17 USC §105).