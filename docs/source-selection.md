# Source selection

Choose the source before touching the estimator. A convenient variable in
the wrong survey is still the wrong variable.

## Decision order

1. Match the concept and its official definition.
2. Match the record unit, universe, denominator, and exclusions.
3. Check geography, period, and known series breaks.
4. Confirm weights, replicate or design variables, imputations, and
   disclosure treatments.
5. Confirm access and redistribution terms.
6. Require a topic-specific official benchmark before publication.

`not available`, `not found`, `not comparable`, `not implemented`, and
`credential required` are different results. Do not collapse them into
"no data."

## Source families

| Need | Strong candidates | Important boundary |
| --- | --- | --- |
| Wealth and balance sheets | SCF | Family unit, five implicates, 999 bootstrap replicates |
| Housing stock and costs | AHS | Housing-unit design; modules and metro samples rotate |
| Spending | Consumer Expenditure | Interview and Diary instruments cover different concepts |
| Income, poverty, programs, labor, time use | ACS PUMS, CPS ASEC, SIPP, ATUS | Person, household, panel, and person-day records are not interchangeable |
| Health spending and coverage | MEPS, OECD SHA | Person-level expenditure is not a national-accounts financing measure |
| Financial experience and attitudes | SHED, GSS | Self-reports are not balance sheets; GSS output has separate terms limits |
| International macro comparisons | OECD, World Bank, Eurostat | Definitions, units, and revision policies differ by dataset |
| Electricity and energy | EIA Form 861, EIA/FRED energy watch | Utility census, market series, and pipeline capacity answer different questions |

## Status is live, not prose

```bash
uv run microdata sources
uv run microdata status
```

The first command reads `config/sources.yaml`; the second reads the current
host's validated release store. Source-selection notes record definitions and
decisions, not a snapshot of one maintainer's machine.

Detailed notes live in [`docs/source-selection/`](source-selection/).
