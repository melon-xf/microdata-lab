# US health expenditure by financing scheme (1970–2023)

## Claim

US health spending as a share of GDP has grown from about 6% in 1970 to
17–18% by 2023, financed primarily by government programs and compulsory
sources (including, after 2014, compulsory private coverage under the ACA).

## Source to replicate

Bruenig, Matt. "The US and the Nordics have similar labor taxes." People's
Policy Project, June 5, 2026 — figure 5 ("sha_financing-1.png").

## Estimand

Current health expenditure (EXP_HEALTH) as a percent of GDP (PT_B1GQ), by
financing scheme, United States, 1970–2023:
- Government programs = HF11 (government schemes) + HF121 (social
  insurance, e.g. Medicare)
- Compulsory private = HF122 (compulsory private insurance, i.e. ESI
  treated as compulsory after the ACA)
- Voluntary private = HF2
- Out-of-pocket = HF3

## Data

OECD System of Health Accounts (DSD_SHA@DF_SHA), measure EXP_HEALTH,
unit PT_B1GQ, REF_AREA=USA, financing schemes HF11/HF121/HF122/HF2/HF3,
TIME_PERIOD 1970–2023.

## Denominator, exclusions, missing

Percent of GDP (B1GQ). Excludes capital formation (DF_SHA_HK) and
COVID-specific schemes. Financing scheme _T (total) is the sum of all
schemes.

## Weight and design

Macrodata; no survey weights.

## Uncertainty

None — official national accounts.

## Benchmark

USA, EXP_HEALTH, PT_B1GQ, 2023 total ≈ 17.2% of GDP (OECD SHA release;
article figure 5 shows ~17–18%).

## Outputs

figure.png + interactive.html, stacked area chart.
