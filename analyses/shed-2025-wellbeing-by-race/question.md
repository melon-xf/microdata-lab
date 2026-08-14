# Question and estimand

## Question

How does self-reported financial well-being vary by race/ethnicity among U.S. households in 2025?

## Estimand

For each race/ethnicity category (`race_5cat`), the weighted share of respondents reporting they are "at least okay financially" (`atleast_okay` == "Yes"), using `weight` as the analysis weight.

## Record unit and universe

- Record unit: SHED respondent (adult in a U.S. household).
- Universe: U.S. adults aged 18+ in the 2025 SHED sample.
- Denominator: all weighted respondents in each race/ethnicity category.
- Exclusions: none beyond missing `race_5cat` or `atleast_okay`.

## Variables and definitions

- `B2`: "Which of the following best describes how well you and your family are managing financially these days?"
  - "Living comfortably" / "Doing okay" → coded as "at least okay" = Yes
  - "Just getting by" / "Finding it difficult to get by" → coded as No
- `race_5cat`: 5-category race/ethnicity: White, Hispanic, Black, Asian, Other.
- `weight`: SHED analysis weight (single-year cross-section).

## Design and uncertainty

SHED provides analysis weights but no replicate weights in the public release. SEs are simple proportion standard errors: $SE = \sqrt{p(1-p)/n}$.

## Release

- Release ID: `shed-2025-9a5cea7a2f8e`
- Official source: Federal Reserve SHED 2025