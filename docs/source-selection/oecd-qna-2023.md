# OECD Statistics — Source Selection Note

## Source
OECD SDMX-JSON API at `https://stats.oecd.org/SDMX-JSON/data/`

## Access
Public, no registration, no authentication. HTTP GET returns SDMX-JSON format.

## Licensing
The [OECD terms](https://www.oecd.org/en/about/terms-conditions.html) permit
extracting, adapting, sharing, and embedding OECD data with attribution unless
a dataset identifies additional third-party restrictions. Raw API responses
stay outside Git.

## Record unit
Macrodata observation (country × indicator × time period).

## Dataset: QNA (Quarterly National Accounts)
- 54 reference areas (OECD member + partner countries)
- 5 transactions (GDP, final consumption, GFCF, exports, imports)
- 3 transformations (period-on-period, year-over-year, cumulative)
- 2 frequencies (quarterly, annual)
- 395 time periods (1947-Q2 through 2026-Q2)

## Weight and design
No weights — macrodata aggregates, not survey microdata.

## Benchmark
USA GDP growth rate (B1GQ, GY, Q) latest observation validated against OECD published value.

## API structure
- Key: `{dataset}/{filter}/all?startTime=...&endTime=...`
- Response: SDMX-JSON with `dataSets[0].series` (series keys → observations)
- Dimensions: returned in `structure.dimensions.series` with index→code mappings
- Observations: returned in `structure.dimensions.observation` (TIME_PERIOD)

## Limitations
- The OECD SDMX-JSON API returns only the latest observation per series when
  startTime/endTime filters are applied. Full historical data requires
  requesting without time filters (large response).
- No API key or registration required.
- The API may return 1533 series for QNA (all countries × all transactions ×
  all transformations), so the normalized Parquet contains all available data.
