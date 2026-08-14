# Source selection — Hormuz energy and inflation watch

## Decision

Use three small FRED-distributed official series plus EIA’s published Hormuz flow workbook. They cover the transmission chain with stable, automatable endpoints and no manual download.

## Matrix

| Concept | Chosen source | Record unit | Frequency | Why it fits | Important limit |
|---|---|---:|---:|---|---|
| Global oil shock | EIA Brent spot price (`DCOILBRENTEU`) via FRED | Trading day | Daily | Global benchmark with direct Persian Gulf exposure | Spot price is not a quantity or causal estimate |
| Consumer fuel bill | EIA regular gasoline (`GASREGW`) via FRED | Publication week | Weekly | National retail price including taxes | Sampled outlets; seasonal and refinery effects remain |
| Medium-term inflation expectations | St. Louis Fed five-year breakeven (`T5YIE`) | Trading day | Daily | Timely market measure built from Treasury yields | Includes risk/liquidity premia; not household expectations |
| Chokepoint exposure | EIA Hormuz figure workbook | Year/quarter | Annual/quarterly | Direct published oil-flow estimate and workbook | Structural baseline, not live vessel tracking |

## Alternatives considered

- **Headline counts:** rejected. Article volume measures editorial attention, not incidents or economic exposure.
- **A proprietary tanker feed:** not selected. It would make the public demo credential-dependent and would not be redistributable.
- **Monthly CPI energy:** useful after release, but too slow to establish the developing path on its own.
- **A generic recession composite:** broader, but less specific. It would trade a clear mechanism for a dashboard of loosely related warnings.

## Provenance and refresh

`energy_watch` downloads keyless CSVs from FRED’s official graph endpoint and the EIA workbook. The normal release pipeline calculates SHA-256 hashes, validates schemas and observation counts, writes a normalized Parquet asset, and promotes atomically. Upstream revisions become new releases.

## Comparability

The chart compares each series with its own pre-disruption value, indexed to 100. That makes relative movement visible; it does not make dollars per barrel, dollars per gallon, and percentage points the same concept. Native frequencies and source dates stay in the table.
