# DX improvements: BLS multi-series adapter, doctor, and scaffolding

Three additions that shorten the path from "new machine" to "running
analysis": a CPI-U multi-series adapter over the official BLS text files, a
`microdata doctor` preflight check, and a `microdata new` analysis scaffold.

## `bls_series` adapter

`src/microdata_lab/adapters/bls_series.py` adapts the complete CPI-U history
published as tab-separated text files under
`https://download.bls.gov/pub/time.series/cu/`. It follows the same contract
as `bls_cpi` and `fred`: `discover()` lists the complete official release,
and the storage layer owns unique incoming runs, SHA-256 hashing, and atomic
promotion. The release comprises four metadata files (`cu.series`, `cu.area`,
`cu.item`, `cu.period`) and 21 observation files (`cu.data.0.Current` ..
`cu.data.20.USCommoditiesServicesSpecial`; file set verified against the live
directory listing in August 2026).

The adapter is registered in `config/sources.yaml` with `enabled: false`: it
is listed by `microdata sources` and syncable by name
(`uv run microdata sync bls_series`), but excluded from `--all` bulk runs
because a full release is 21 large files behind the BLS firewall. Enable it
deliberately when an analysis needs it.

### The BLS firewall

`download.bls.gov` rejects generic User-Agents with an HTML block page
(HTTP 403, ~29 lines, starts with `<!DOCTYPE HTML>`). Requests succeed only
with the identifying `BLS_USER_AGENT` from
`~/.config/microdata-lab/.env` (configure with
`uv run python scripts/configure_bls_contact.py`). Every download path fails
loudly when it sniffs `<html`/`<!doctype` at the start of a payload — or an
implausibly small `cu.data.*` file — and the error names `BLS_USER_AGENT` and
the remediation script. Block pages never reach the release store.

### Verified file layouts

- `cu.series`: series_id (space-padded to the tab), area_code, item_code,
  seasonal, periodicity_code, base_code, base_period, series_title,
  footnote_codes, begin_year, begin_period, end_year, end_period.
- `cu.area` / `cu.item`: code, name, display_level, selectable, sort_sequence.
- `cu.period`: period, period_abbr, period_name (CRLF endings).
- `cu.data.*`: series_id (padded), year, period, value (space-padded),
  footnote_codes; CRLF endings.

Series-id grammar: `CU` + seasonal (`U`/`S`) + periodicity (`R`) + area_code
+ item_code — e.g. `CUURS49ESEFV` = CU·U·R·S49E (San Diego-Carlsbad)·SEFV
(Food away from home). Always join on `cu.series` rather than parsing ids;
area codes vary in length.

### Periodicity semantics

- `M01`–`M12`: monthly index observations, resolved to ISO month timestamps
  (`YYYY-MM-01`) in the `date` column.
- `M13`: annual average of the twelve monthly indexes. Not an observation;
  `date` is empty.
- `S01`/`S02`: semiannual averages; `S03`: annual average computed from
  semiannual indexes (some older MSA series). Never resolved to a month.
- Average periods are excluded from `fetch_series()` unless
  `include_averages=True`.
- Some MSA series publish bimonthly (odd or even months only); those rows
  keep `M01`–`M12` codes and the gaps are genuine non-publication.

### Public API

```python
from microdata_lab.adapters.bls_series import BlsSeriesAdapter

with BlsSeriesAdapter() as adapter:
    catalog = adapter.fetch_catalog()          # {"series", "areas", "items", "periods"}
    fafh = adapter.fetch_series(
        area_codes=["S49A", "S49E"],           # west-coast MSAs
        item_codes=["SEFV"],                   # food away from home
        data_files=["cu.data.10.OtherWest"],   # optional scan restriction
    )
```

`fetch_series` returns a tidy DataFrame: `series_id, date, period, year,
value, area_code, area_name`, with geography resolved from `cu.area`.
Selection is by explicit `series_ids` or by catalog filters (`area_codes`,
`item_codes`, `seasonal`); without a scan restriction all 21 data files are
streamed. The release benchmark gate reproduces `CUURS49ASEFV` 1952-12 = 20.8
(Los Angeles food away from home, first published month).

## `microdata doctor`

Prints a PASS/FAIL table and exits nonzero on any failure:

1. `MICRODATA_ROOT` exists and is writable.
2. `.env` keys present — `BLS_USER_AGENT`, `FRED_API_KEY`, `CENSUS_API_KEY`,
   `IPUMS_API_KEY`. Names only; values are never printed.
3. `.r-env/bin/Rscript` runs (`--version`).
4. A playwright chromium build exists under `~/.cache/ms-playwright`. The
   check mirrors playwright's own resolution logic, which keys off `$HOME`
   (and honors `PLAYWRIGHT_BROWSERS_PATH` implicitly through it): if browsers
   were installed under one home directory but you run from another,
   `microdata doctor` will flag it just like playwright would fail at launch
   time. Reinstall with `uv run npx playwright install chromium` for the
   active `$HOME`, or align `PLAYWRIGHT_BROWSERS_PATH`.
5. `download.bls.gov` serves `cu.series` as text with the identifying
   User-Agent; an HTML block page is a FAIL with the `BLS_USER_AGENT`
   remediation hint.
6. FRED API ping (`/fred/series?series_id=GNPCA`); the API key is never
   echoed.

## `microdata new <slug>`

Scaffolds `analyses/<slug>/` with the AGENTS.md contract files:
`question.md` (estimand, universe, variables, design, assumptions, release
IDs, benchmark), an `estimate.py` template that imports `microdata_lab` and
writes `data.csv`/`diagnostics.json`, a minimal valid `chart.yaml`, and a
`README.md` marked as generated. The command refuses to clobber an existing
directory and rejects slugs outside `[a-z0-9_][a-z0-9_-]*`.
