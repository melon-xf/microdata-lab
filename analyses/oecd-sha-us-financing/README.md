# US Health Expenditure by Financing Scheme, 1970–2023

Replicates a published figure 5 (`sha_financing-1.png`).

## Finding

US health spending grew from about 6% of GDP in 1970 to roughly 17–18% by
2023. Government programs finance the largest share; a distinct
"compulsory private" band (employer-sponsored coverage treated as
compulsory under the ACA) appears after 2014.

## Data

- OECD System of Health Accounts (`DSD_SHA@DF_SHA`), measure
  `EXP_HEALTH` (current health expenditure), unit `PT_B1GQ` (percent of
  GDP), REF_AREA = USA, financing schemes HF11 (government), HF121/HF122
  (compulsory private), HF2 (voluntary private), HF3 (out-of-pocket),
  1970–2023.
- Release: `oecd_sha-2023`.

## Method

Percent of GDP by financing scheme; HF121+HF122 summed into the
"Compulsory private" band. Official national accounts — no sampling
variance.

## Files

- `estimate.py`, `data.csv`, `diagnostics.json`, `chart.yaml`,
  `figure.png`, `interactive.html`
