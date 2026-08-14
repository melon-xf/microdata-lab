# Question — Hormuz, energy prices, and inflation expectations

## Estimand

Change in three published market indicators since the last observation on or before February 27, 2026, the day before U.S.-Israeli military action against Iran began:

- Brent crude oil spot price, dollars per barrel;
- U.S. regular gasoline price, dollars per gallon;
- five-year breakeven inflation rate, percent.

Each series is also indexed to 100 at its own pre-disruption observation so their paths can be compared without pretending the units are interchangeable.

## Why these links

EIA estimates that 20 million barrels per day crossed the Strait of Hormuz in 2024, while only 2.6 million barrels per day of spare pipeline capacity could bypass it. The St. Louis Fed dates reported tanker damage and obstruction to March 1, 2026. Brent records the oil-market shock, gasoline shows the consumer energy bill, and the breakeven rate tests whether medium-term market inflation expectations moved with them.

## Record unit and period

One daily or weekly observation, depending on the source series, from February 2026 through the latest validated release. The three series keep their native publication frequency. They are not interpolated onto a fake common calendar.

## Sources and definitions

- `DCOILBRENTEU`: daily Brent crude spot price, EIA, distributed by FRED.
- `GASREGW`: weekly U.S. regular gasoline price, EIA, distributed by FRED. EIA describes it as a weighted average from a sample of roughly 900 retail outlets.
- `T5YIE`: daily five-year breakeven inflation rate, Federal Reserve Bank of St. Louis. It is derived from nominal and inflation-indexed Treasury yields.
- Hormuz baseline: EIA *Today in Energy*, June 16, 2025, including the published figure workbook.

## Design

This is a continuously refreshed descriptive watch, not an event-study estimate. The adapter downloads all four official artifacts into a unique incoming run, hashes and validates them, and promotes a new immutable release only after every check passes. `estimate.py` then rebuilds the indexed series and diagnostics from the promoted Parquet asset.

## Limits

- The event date does not isolate a causal effect. Oil prices also respond to global demand, production decisions, inventories, sanctions, and expectations.
- Gasoline is weekly and can lag oil for operational reasons. The chart does not estimate pass-through.
- Breakeven inflation includes inflation risk and liquidity premia. It is not a survey of household expectations.
- The EIA Hormuz exposure estimate is a structural baseline, not a live tanker count.
- Latest observations arrive on different dates. Every value carries its own publication date.

## Release

The exact `energy_watch` release ID and source checksums are recorded in `diagnostics.json` after each refresh.
