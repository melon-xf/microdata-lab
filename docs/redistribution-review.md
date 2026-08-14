# Provider redistribution boundary

Checked against the linked provider terms on August 14, 2026. This is a repository rule, not legal advice. Recheck a provider's current terms before adding a new dataset or changing what the repository publishes.

## The line

The repository may contain code, source metadata, analysis contracts, diagnostics, non-disclosive aggregate chart tables, and rendered charts when the provider permits publication with the required attribution.

It must not contain raw microdata, normalized person-level extracts, full API responses copied from a restricted provider, credentials, or source documents whose reuse rights are unresolved.

## Source rules

| Source family | Public-repository rule |
|---|---|
| SCF and SHED | Keep respondent-level files outside Git. Publish code and aggregate results with Federal Reserve attribution. |
| ACS PUMS, CPS ASEC, and ATUS through IPUMS | Users supply their own account, collection registration, and API key. Do not commit IPUMS extracts or normalized derivatives. |
| SIPP and AHS | Keep public-use microdata outside Git. Publish code, diagnostics, and non-disclosive aggregate results with Census or HUD attribution. |
| CE and BLS CPI | Keep CE microdata outside Git. BLS-derived aggregate tables may ship with source and release information. |
| MEPS | Keep person-level public-use files outside Git. Publish aggregate results with AHRQ attribution and the release identifier. |
| GSS | NORC's terms require permission to reproduce website contents. Keep the adapter and access documentation public, but do not ship GSS-derived data tables, charts, or copied documentation without written permission. |
| OECD QNA, Taxing Wages, and SHA | [OECD terms](https://www.oecd.org/en/about/terms-conditions.html) permit extracting, adapting, sharing, and embedding data with attribution unless a dataset identifies additional third-party restrictions. Keep raw API responses outside Git; retain dataset citations in aggregate outputs. |
| World Development Indicators | The [WDI catalog entry](https://datacatalog.worldbank.org/search/dataset/0037712/World-Development-Indicators) lists the dataset as CC BY 4.0. Aggregate chart data may ship with World Bank attribution. |
| Eurostat | [Eurostat permits commercial and non-commercial reuse](https://ec.europa.eu/eurostat/help/copyright-notice) with source acknowledgment, subject to listed exceptions. |
| WHO | [WHO dataset terms](https://data.who.int/about/data/terms-and-conditions) use CC BY 4.0 unless a dataset says otherwise. Check the dataset metadata and preserve the required citation. |
| ILOSTAT | Keep downloaded responses outside Git unless the specific dataset's reuse terms are recorded. Publish query definitions and links. |
| FRED | [FRED's API terms](https://fred.stlouisfed.org/docs/api/terms_of_use.html) defer to each series owner. Check the series notes before publishing values. The retained energy-watch series identify U.S. government sources and carry source attribution. |
| Census API | Do not commit keys. Aggregate Census API results may ship with the dataset name, vintage, query, and Census attribution. |
| EIA | [EIA data and files may be reused](https://www.eia.gov/about/copyrights_reuse.php) with acknowledgment unless a specific item says otherwise. Do not reuse EIA logos or separately licensed media. |
| NLRB | The adapter is not implemented. No NLRB release data ships until the adapter and a source-specific terms review exist. |

## Historical material

The rural-electrification analysis uses values transcribed from USDA *Agricultural Statistics*. The repository contains citations, calculations, aggregate values, and rendered charts. It does not contain the third-party scans or copied pages used to verify the tables.

## Before adding an artifact

1. Identify the provider and exact dataset, not just the API host.
2. Record the controlling terms URL and the date checked.
3. Separate raw/provider files from non-disclosive publication aggregates.
4. Keep credentials and restricted files outside Git.
5. Add the required citation to `question.md`, `diagnostics.json`, and the rendered artifact.
6. Stop the release if the rights are unclear; do not treat public download access as permission to redistribute.
