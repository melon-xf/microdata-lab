# CPS ASEC — Source Selection Note

## Source
Current Population Survey Annual Social and Economic Supplement (CPS ASEC),
U.S. Census Bureau and Bureau of Labor Statistics.
Accessed via IPUMS CPS extract system: `https://cps.ipums.org`

## Access
IPUMS requires a free API key (`IPUMS_API_KEY`). CPS public-use files are
public domain (U.S. federal government work). IPUMS redistribution terms
require attribution and prohibit redistribution of IPUMS-formatted extracts.

## Record unit
Person (linked to household and family records).

## Universe
U.S. civilian non-institutionalized population. ASEC supplement covers
the preceding calendar year's income, employment, and health insurance.

## Weight
`ASECWT` — ASEC person weight. `ASECWTH` for household-level analysis.
`HWTFINA` for basic monthly CPS.

## Design variables
- `STRATA`: stratification
- `CLUSTER`: PSU cluster

## Replicate weights
Not provided in CPS ASEC PUMS. Taylor-series variance using `STRATA` and
`CLUSTER` is the documented approach.

## Geography and years
State and sub-state (metro/non-metro). Annual 1962–2025 available via IPUMS.

## Known breaks and limitations
- 2014: new processing system introduced; health insurance coverage
  estimates not comparable to prior years.
- 2019: ASEC sample expansion and weight recalibration.
- 2020: pandemic data collection disruption.
- Income and poverty estimates differ from official Census/JSAM methodology
  due to public-use disclosure limitations.

## Validation contract
The adapter requires the IPUMS extract, codebook, DDI metadata, replicate
weights, and a weighted-population benchmark before promotion. Run
`uv run microdata status` to inspect releases available on the current host.