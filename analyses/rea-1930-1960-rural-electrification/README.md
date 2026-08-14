# REA rural electrification, 1930–1963

## Result

Percent of U.S. farms receiving central-station electric service (USDA
Agricultural Statistics / REA annual estimates):

| Year | Percent of farms | Farms (n) | Source |
|---|---|---|---|
| 1930 | 9.1% | 571,007 | Census of Agriculture 1930, as tabulated in Ag. Stats 1940, Table 745 |
| 1934 | 10.9% | 743,954 | Ag. Stats 1950, Table 742 |
| 1940 | 30.4% | 1,853,249 | Ag. Stats 1950, Table 742 |
| 1945 | 47.9% | 2,806,206 | Ag. Stats 1950, Table 742 |
| 1949 | 78.2% | 4,582,016 | Ag. Stats 1950, Table 742 |
| 1954 | 92.3% | 4,965,962 | Ag. Stats 1955, Table 777 |
| 1960 | 96.5% | 3,579,650 | Ag. Stats 1961, Table 807 |
| 1963 | 97.9% | 3,505,300 | Ag. Stats 1964, Table 813 |

Private capital reached ~9% of farms in the four decades to 1930 (and
~10.9% by end-1934). The REA, chartered May 1935, with loans at roughly 2%
interest, took that to 30.4% by April 1940 — and 96.5% by 1960. The
absolute number of electrified farms peaked around 1954 (4.97M) and then
fell as farm consolidation shrank the total farm count; the *share* kept
climbing to 97.9% by 1963.

## Methods

- Every data point was read directly from the scanned USDA Agricultural
  Statistics yearbook on archive.org: `sim_agricultural-statistics_1940`,
  `sim_agricultural-statistics_1950`, `agriculturalstat00unic` (1955),
  `sim_agricultural-statistics_1961`, `sim_agricultural-statistics_1964`.
  Values were verified at the word-coordinate level against each scan's OCR
  layer (`_djvu.xml`) — e.g. the 1950 edition's U.S. row reads
  "743,954 10.9 / 1,853,249 30.4 / 2,806,206 47.9 / 4,582,016 78.2" and the
  published "increase from Dec 31, 1934" column (3,838,062) equals
  4,582,016 − 743,954 exactly.
- Definition: "farms receiving central-station electric service" — REA
  annual estimates as a share of the Census of Agriculture farm count (the
  tables' footnotes name the census years: 1930/1945/1950/1959 censuses).

## Benchmark

Internal-consistency checks on the published figures (see diagnostics):

1. Ag. Stats 1950 Table 742's published increase column (3,838,062) is
   exactly 4,582,016 − 743,954 → PASS.
2. 4,582,016 / 0.782 = 5.86M farms ≈ the 1945 Census farm count
   (5,859,169), the table's stated denominator → PASS.
3. 3,579,650 / 0.965 = 3.71M farms ≈ the 1959 Census farm count
   (3,703,894), the table's stated denominator → PASS.

## Limitations

- The pre-REA "market failure" framing is the standard account: private
  utilities skipped rural areas because of low load density and high
  per-customer line cost; the REA worked because the federal government
  took the risk and subsidized financing (loans at ~2%).
- The commonly cited 1940 figure of 33.2% (Census of Agriculture, farm
  dwellings with electricity) differs from the 30.4% central-station
  estimate used here; the two definitions are both official and both show
  the same breakneck 1935–1940 acceleration.
- A TVA average-residential-rate comparison was considered as a second
  series but could not be tied to a citable TVA publication. It is omitted.

## Sources

- USDA, *Agricultural Statistics 1940*, Table 745 ("Electric service: Number
  and percentage of farms receiving central-station electric service… June
  30, 1939, with comparisons for earlier years"); archive.org item
  `sim_agricultural-statistics_1940`.
- USDA, *Agricultural Statistics 1950*, Table 742 ("Rural Electrification
  Administration: Number and percentage of farms receiving central-station
  electric service, by States, for specified dates"); archive.org item
  `sim_agricultural-statistics_1950`.
- USDA, *Agricultural Statistics 1955*, Table 777 (as of June 30, 1954);
  archive.org item `agriculturalstat00unic`.
- USDA, *Agricultural Statistics 1961*, Table 807 (as of June 30, 1960);
  archive.org item `sim_agricultural-statistics_1961`.
- USDA, *Agricultural Statistics 1964*, Table 813 (as of June 30, 1963);
  archive.org item `sim_agricultural-statistics_1964`.
