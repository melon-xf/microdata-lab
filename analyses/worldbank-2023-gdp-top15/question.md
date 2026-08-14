# Question and estimand

## Question

Which countries had the largest economies by GDP (current US$) in 2023?

## Estimand

GDP at current market prices in US dollars for the 15 largest economies in 2023.

## Record unit and universe

- Record unit: country-year observation.
- Universe: all sovereign countries with GDP data reported to the World Bank for 2023.
- Exclusions: regional aggregates (e.g., "World", "High income", "EU") excluded; only individual countries included.

## Variables and definitions

- `NY.GDP.MKTP.CD`: GDP at market prices (current US$), World Bank indicator.
- `country_name`: Official World Bank country name.
- `countryiso3code`: ISO 3166-1 alpha-3 country code.

## Design and uncertainty

No survey design. Administrative/official macrodata — no sampling variance.

## Release

- Release ID: `worldbank-2023-b913afa94f69`
- Source: World Bank Open Data API v2
- URL: `https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.CD`