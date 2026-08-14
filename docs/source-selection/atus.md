# ATUS — Source Selection Note

## Source
American Time Use Survey (ATUS), Bureau of Labor Statistics.
Accessed via IPUMS ATUS extract system: `https://timeuse.ipums.org`

## Access
IPUMS requires a free API key (`IPUMS_API_KEY`). ATUS public-use files are
public domain (U.S. federal government work). IPUMS redistribution terms
require attribution and prohibit redistribution of IPUMS-formatted extracts.

## Record unit
Person-day (time-use diary).

## Universe
U.S. civilian non-institutionalized population aged 15+.

## Weight
`WT06` — ATUS person-day weight. Sums to the U.S. population aged 15+.

## Design variables
- `STRATA`: stratification
- `CLUSTER`: PSU cluster

## Replicate weights
Not provided in ATUS PUMS. Taylor-series variance using `STRATA` and
`CLUSTER` is the documented approach.

## Geography and years
National and 4 Census regions. Annual 2003–2025 available via IPUMS.
Some years include state identifiers for select states.

## Known breaks and limitations
- 2020: pandemic collection disruption; lower response rates.
- Activity coding system updates: pre-2008 and 2008+ use different
  activity taxonomies; cross-year comparability requires care.
- Time-use diary covers a single designated day per respondent.

## Validation contract
The adapter requires the IPUMS extract, codebook, DDI metadata, replicate
weights, and a weighted-population benchmark before promotion. Run
`uv run microdata status` to inspect releases available on the current host.