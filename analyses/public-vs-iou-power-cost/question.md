# Question — Public vs investor-owned power: the empirical record

## Estimand
The revenue-weighted average residential electricity price paid by
customers of publicly owned (municipal) utilities vs investor-owned
utilities (IOUs), U.S., calendar year 2024 — with the TVA-area distributors'
average and the all-owners U.S. average as reference points — plus the
peer-reviewed literature on public vs private utility costs.

## Why
Ownership is often argued in the abstract. This analysis asks a narrower
question that official data can answer: what did customers of municipal and
investor-owned utilities pay for residential electricity in 2024?

## Universe
All U.S. utilities reporting residential sales to ultimate customers on EIA
Form 861 (2024), grouped by the EIA-861 ownership classification
(Municipal = publicly owned; Investor Owned; Cooperative; Federal). The
TVA-area figure covers utilities whose balancing-authority code is TVA
(municipal and cooperative distributors buying TVA power in 7 states).

## Variables
- `RES_Rev`: residential revenues ($1000), `RES_Sales`: residential sales
  (MWh) — EIA-861 Sales to Ultimate Customers.
- Average price = Σrevenue / Σsales × 100 (cents per kWh).

## Design
- Observed rows only (Data Type = O), all service types (bundled + energy
  + delivery, so the full retail bill is captured in restructured states).
- Immutable source release: `eia_861-2024-aca25b50f1cb`.
- Revenue-weighted aggregation per ownership class.
- Benchmark: computed all-owners U.S. average vs the official EIA Electric
  Power Monthly 2024 annual residential average (16.48 c/kWh, Table 5.3);
  gate ±10%.

## Assumptions / limitations
- Observational comparison, not causal: ownership correlates with service
  area, state mix, and cost structure.
- TVA-area figure is the retail footprint of TVA's distributor customers,
  not TVA's wholesale rate (TVA reports no retail sales in EIA-861).
- EIA-861 computed U.S. average (15.41) is ~6% below the EPM aggregate
  (16.48) because a small share of sales appears only in the state-level
  EPM aggregation; documented in diagnostics, gate passes.
- Literature pillar: Kwoka (2005) cited for the qualitative finding (public
  advantage in distribution); the paper's numeric coefficients are
  paywalled and are not reproduced.

## Sources
- EIA Form 861 (2024), Sales to Ultimate Customers
  (https://www.eia.gov/electricity/data/eia861/zip/f8612024.zip).
- EIA Electric Power Monthly, Table 5.3 (2024 annual averages).
- Kwoka, J. (2005), Canadian Journal of Economics 38(2): 622–640.
