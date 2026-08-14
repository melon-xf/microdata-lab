# ACS PUMS — Source Selection Note

## Source
American Community Survey Public Use Microdata Sample (ACS PUMS), U.S. Census Bureau.
Accessed via IPUMS USA extract system: `https://usa.ipums.org`

## Access
IPUMS requires a free API key (`IPUMS_API_KEY`). Census Bureau PUMS files are public
domain (U.S. federal government work). IPUMS redistribution terms require attribution
and prohibit redistribution of unmodified IPUMS-formatted extracts.

## Record unit
Person and household.

## Universe
U.S. resident population living in housing units and group quarters.

## Weight
`PERWT` (person weight), `HHWT` (household weight).

## Design variables
- `STRATA`: stratification variable
- `CLUSTER`: cluster variable (household serial)
- PUMAs: Public Use Microdata Areas (minimum geography, ~100K population)

## Replicate weights
Not provided in ACS PUMS. Design-based (Taylor series) variance estimation using
`STRATA` and `CLUSTER` is the documented approach.

## Geography and years
PUMA-level (sub-state, ~100K population). Annual 2005–2024 available.

## Known breaks and limitations
- PUMA boundaries redrawn after 2020 Census; pre-2020 PUMAs not comparable to 2020+.
- 2020 ACS experimental due to pandemic collection disruptions.
- Group quarters population underrepresented in 2020.

## Validation contract
The adapter requires the IPUMS extract, codebook, DDI metadata, replicate
weights, and a weighted-population benchmark before promotion. Run
`uv run microdata status` to inspect releases available on the current host.