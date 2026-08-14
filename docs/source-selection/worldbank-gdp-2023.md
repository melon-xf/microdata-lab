# World Bank Open Data — Source Selection Note

## Source
World Bank API v2 at `https://api.worldbank.org/v2/`

## Access
Public, no registration, no authentication. Returns JSON with metadata page
and data page.

## Licensing
The World Development Indicators catalog entry identifies the dataset as
[CC BY 4.0](https://datacatalog.worldbank.org/search/dataset/0037712/World-Development-Indicators).
Published aggregates retain World Bank attribution; raw API responses stay
outside Git.

## Record unit
Macrodata observation (country × indicator × year).

## Indicator: NY.GDP.MKTP.CD (GDP current US$)
- 265 country/region observations per year
- Annual data; the release manifest records the API's `lastupdated` value
- Values in current US dollars

## Weight and design
No weights — macrodata aggregates.

## Benchmark
USA GDP (NY.GDP.MKTP.CD) for reference year validated against World Bank published value.

## API structure
- Endpoint: `/v2/country/all/indicator/{indicator}?format=json&date={year}&per_page=...`
- Response: `[metadata_page, data_page]`
- Pagination: `per_page` up to 1000; total pages in metadata
- Data fields: `country.value`, `countryiso3code`, `date`, `value`, `indicator.id`

## Limitations
- Some country/region aggregates included (e.g., "Arab World", "Africa Eastern...")
- Missing values returned as `null`
