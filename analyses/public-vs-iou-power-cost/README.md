# Public vs investor-owned power: the empirical record

## Result

Revenue-weighted average residential electricity price, 2024, from EIA Form
861 utility-level data (observed rows, all service types):

| Category | Average residential price | Note |
|---|---|---|
| TVA-area distributors (public power) | **12.43 ¢/kWh** | municipal + cooperative utilities buying TVA power, 7 states |
| Municipal utilities (publicly owned) | **13.53 ¢/kWh** | 457 utilities |
| U.S. average (all owners) | 15.41 ¢/kWh | computed from EIA-861 |
| Investor-owned utilities (IOUs) | **16.50 ¢/kWh** | 187 utilities |

IOU customers paid **22% more** per residential kilowatt-hour than
municipal-utility customers in 2024 (16.50 vs 13.53; municipal 18% lower).
Customers of TVA's public-power distributors paid 12.43 — 24% below the
computed national average.

This comparison puts a number on ownership. It is observational — municipal
systems are concentrated in different service areas than IOUs — but the
pattern is clear in the 2024 data: public utilities charged less, on average,
for residential power.

## Literature pillar (a)

Kwoka, John (2005). "The comparative advantage of public ownership:
evidence from U.S. electric utilities." *Canadian Journal of Economics /
Revue canadienne d'économique* 38(2): 622–640.
doi:10.1111/j.0008-4085.2005.00296.x.

Published finding (abstract, verified via the IAEA INIS and OSTI records):
*"while privately owned systems achieve lower costs in generation, public
systems generally have an advantage in the end-user-oriented distribution
function with its more non-contractible quality attributes."*

The paper's specific cost coefficients sit behind the publisher's paywall
and are not reproduced here. Its qualitative finding is cited with full
attribution; the quantitative result in this analysis comes from the
official EIA-861 computation above.

## Data pillar (b)

EIA Form 861 (2024), Sales to Ultimate Customers, acquired and validated by
the `eia_861` adapter as release `eia_861-2024-aca25b50f1cb`. The official
ZIP has SHA-256
`77ce49c60ac5a6bad50c442fc401aad5404a21da875dc5cbaba353af5ede54de`;
the source URL and access date are recorded in diagnostics. Utility-level
residential revenues and sales are summed by EIA-861 ownership class.

- Municipal = publicly owned utilities (457 utilities in the 2024 file).
- TVA-area = utilities whose balancing-authority code is TVA (107 municipal
  + 57 cooperative + 5 federal), covering ~4% of U.S. residential sales.
- IOU = investor-owned (187 utilities).
- All figures are revenue-weighted averages (Σ$ / ΣMWh × 100).

## Benchmark

Computed U.S. residential average from EIA-861: 15.41 ¢/kWh vs the official
EIA Electric Power Monthly 2024 annual average (16.48 ¢/kWh, Table 5.3) —
ratio 0.935 within the ±10% gate → **PASS**. The gap is expected: a small
share of residential sales appears only in the state-level EPM aggregation,
not in the utility-level EIA-861 rows.

## Limitations

- Observational, not causal: municipal and IOU service areas differ in cost
  structure, state mix, and urban/rural composition. The comparison is a
  pattern in official data, not an experiment.
- TVA sells almost no retail in EIA-861 (it is a wholesale supplier); the
  "TVA-area" figure is the retail footprint of its distributor customers.
- Residential-only comparison; industrial and commercial excluded.
- Kwoka's coefficients are not reproduced (paywalled; see above).

## Sources

- U.S. EIA, Form 861 (2024), Sales to Ultimate Customers,
  https://www.eia.gov/electricity/data/eia861/zip/f8612024.zip (accessed
  2026-08-07).
- U.S. EIA, [Copyrights and Reuse](https://www.eia.gov/about/copyrights_reuse.php)
  (accessed 2026-08-14). EIA states that its data and files may be used and
  distributed with an acknowledgment; this repository retains the source,
  date, and checksum above.
- U.S. EIA, Electric Power Monthly, Table 5.3, 2024 annual averages,
  https://www.eia.gov/electricity/monthly/xls/table_5_03.xlsx (accessed
  2026-08-07).
- Kwoka, J. (2005), Canadian Journal of Economics 38(2): 622–640.

*EIA acknowledgment: "U.S. Energy Information Administration (EIA), Form
861 data, 2024." Analyses derived from EIA data acknowledge EIA as the
source and are not endorsed by EIA.*
