# Adding a source adapter

This guide walks through implementing a new source adapter for the microdata platform. Every adapter follows the same contract defined in `src/microdata_lab/adapters/base.py`.

## Adapter contract

Each adapter subclasses `SourceAdapter` and implements:

| Method | Required | Purpose |
|--------|----------|---------|
| `discover(year)` | Yes | Parse the official release surface and return a `DiscoveredRelease` with all required artifacts. Fail visibly if any role is missing. |
| `available_years()` | No | Return list of years for backfill. Default: current year only. |
| `validate_release()` | No | Run source-specific gates: row counts, weights, design variables, benchmarks. |
| `normalize_release()` | No | Write analysis-ready Parquet derivatives under the incoming run. |
| `download_client()` | No | Return authenticated `httpx.Client` when provider-specific headers or auth are needed. |
| `close()` | No | Release network or provider resources. |

## Steps

### 1. Register the source

Add the source to `config/sources.yaml` with authoritative landing page, access mode, record unit, cadence, and design artifacts:

```yaml
  my_source:
    name: Full Survey Name
    agency: Agency Name
    landing_page: https://agency.gov/data
    access: public  # or: licensed_api
    adapter: my_source
    implemented: false  # set to true after all gates pass
    record_unit: household  # or: person, person-month, country-year
    weight_column: WEIGHT_VAR
    replicate_weights: true  # or false
```

### 2. Create the source config

Create `config/sources/my_source.yaml` with discovery parameters (URLs, patterns, year, benchmark values).

### 3. Implement the adapter

Create `src/microdata_lab/adapters/my_source.py`:

```python
from __future__ import annotations
from pathlib import Path
from microdata_lab.adapters.base import SourceAdapter
from microdata_lab.models import (
    DiscoveredRelease,
    DiscoveredArtifact,
    StoredArtifact,
    ValidationResult,
)


class MySourceAdapter(SourceAdapter):
    slug = "my_source"

    def discover(self, year: int | None = None) -> DiscoveredRelease:
        # 1. Parse the official release page or API
        # 2. Classify every required artifact by role
        # 3. Return DiscoveredRelease or raise on missing roles
        ...

    def validate_release(self, run_root, release, artifacts) -> ValidationResult:
        # Check row counts, weights, design variables
        # Reproduce an official benchmark
        # Return ValidationResult with pass/fail checks dict
        ...

    def normalize_release(self, run_root, release, artifacts) -> list[Path]:
        # Write Parquet derivatives under run_root / "normalized"
        ...
```

### 4. Register in the adapter factory

Add the adapter to `src/microdata_lab/adapters/__init__.py`:

```python
from microdata_lab.adapters.my_source import MySourceAdapter
ADAPTERS = {
    ...
    "my_source": MySourceAdapter,
}
```

### 5. Write tests

Create `tests/test_my_source_adapter.py` with:
- Mocked discovery test (no network)
- Malicious archive test (zip bomb, path traversal)
- Role-presence validation
- Benchmark reproduction (when data is available)

Update `tests/test_adapter_registry.py` with the new slug.

### 6. Sync, validate, and promote

```bash
uv run microdata sync my_source --year 2024
uv run microdata validate my_source
uv run microdata scrub
```

### 7. Set `implemented: true`

Only after all gates pass and the release is promoted.

## Credentialed APIs

If access requires an account or API key:
1. Expose the environment variable in `.env.example`
2. Document the official signup URL
3. Stop with an actionable credential error if missing
4. Never switch to an inferior public mirror or ask the user to manually download

Read credentials from the environment at runtime:

```python
import os

api_key = os.environ.get("MY_SOURCE_API_KEY")
if not api_key:
    raise RuntimeError("Set MY_SOURCE_API_KEY. Sign up at https://agency.gov/api")
```

## Common patterns

### Macrodata (no survey design)

For API-based macrodata (OECD, World Bank, Eurostat):
- `discover()` hits the API and returns a single JSON/CSV artifact
- `normalize_release()` flattens the API response to a tidy Parquet file
- `validate_release()` checks observation count and a known value
- No weights, replicate weights, or imputation flags

### US federal microdata (public domain)

For Census, BLS, and AHRQ sources (17 USC §105):
- Public domain, redistribution permitted
- Standard survey design: person/household weight, optional replicate weights
- Benchmark against published tables (e.g., BLS Table 2500 for CE)

### Licensed extracts (IPUMS)

For IPUMS-accessed sources (ACS, CPS, ATUS):
- User-specific API key required
- Terms restrict redistribution of the extract
- Normalized data stays in `$MICRODATA_ROOT`, never in the repository
- Analysis code references releases by ID, not hardcoded paths

### Copyright-restricted (NORC/GSS)

For GSS:
- Data is freely downloadable but NORC retains copyright
- Adapter sets `redistributable: false` in release metadata
- Personal-use-only flag marks releases as non-redistributable
- Works for local analysis but must not ship in public releases