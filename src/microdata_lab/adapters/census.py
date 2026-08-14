from __future__ import annotations

import json
from pathlib import Path

import httpx
import pandas as pd
import yaml
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, TypeAdapter

from microdata_lab.adapters.base import SourceAdapter
from microdata_lab.models import (
    DiscoveredArtifact,
    DiscoveredRelease,
    StoredArtifact,
    ValidationResult,
)
from microdata_lab.secrets import require_secret

API_BASE = "https://api.census.gov/data"
DEFINITION_PATH = Path(__file__).resolve().parents[3] / "config/census/acs-population.yaml"
_url_adapter = TypeAdapter(AnyHttpUrl)

DATA_JSON = "data_json"


class CensusBenchmark(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variable: str
    geo: str
    expected_value: float | None = None
    tolerance: float = 0.001
    description: str = ""


class CensusConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: str
    dataset_title: str
    variables: list[str]
    landing_page: AnyHttpUrl
    reference_year: int
    benchmark: CensusBenchmark
    terms: str = "census_public_domain"
    record_unit: str = "table_estimate"
    credential: str = "CENSUS_API_KEY"


class CensusAdapter(SourceAdapter):
    slug = "census"

    def __init__(
        self,
        *,
        definition: CensusConfig | None = None,
        client: httpx.Client | None = None,
        api_key: str | None = None,
    ) -> None:
        self.definition = definition or _load_definition(DEFINITION_PATH)
        self._client = client
        self._api_key = api_key

    @property
    def api_key(self) -> str:
        if self._api_key is None:
            self._api_key = require_secret(self.definition.credential)
        return self._api_key

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                follow_redirects=True,
                timeout=120,
                headers={"User-Agent": "microdata-lab/1.0"},
            )
        return self._client

    def available_years(self) -> list[int]:
        return [self.definition.reference_year]

    def discover(self, year: int | None = None) -> DiscoveredRelease:
        selected_year = year or self.definition.reference_year
        variables = ",".join(self.definition.variables)
        url = (
            f"{API_BASE}/{selected_year}/{self.definition.dataset}"
            f"?get={variables}&for={self.definition.benchmark.geo}:1"
            f"&key={self.api_key}"
        )
        return DiscoveredRelease(
            survey=self.slug,
            year=selected_year,
            landing_page=self.definition.landing_page,
            artifacts=[
                DiscoveredArtifact(
                    role=DATA_JSON,
                    url=_url_adapter.validate_python(url),
                    filename=(
                        f"census_{self.definition.dataset.replace('/', '_')}_{selected_year}.json"
                    ),
                    link_text=f"Census {self.definition.dataset_title} {selected_year}",
                )
            ],
            source_metadata={
                "record_unit": self.definition.record_unit,
                "dataset": self.definition.dataset,
                "variables": self.definition.variables,
                "api": "Census Data API",
                "terms": self.definition.terms,
                "credential": self.definition.credential,
            },
        )

    def validate_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> ValidationResult:
        checks: dict[str, bool] = {}
        notes: list[str] = []

        json_path = None
        for a in artifacts:
            if str(a.role) == DATA_JSON:
                json_path = run_root / a.relative_path
                break
        if json_path is None or not json_path.exists():
            checks["census_json_present"] = False
            return ValidationResult(passed=False, checks=checks, notes=notes)
        checks["census_json_present"] = True

        with json_path.open() as f:
            payload = json.load(f)
        if not isinstance(payload, list) or len(payload) < 2:
            checks["census_rows_present"] = False
            return ValidationResult(passed=False, checks=checks, notes=notes)
        checks["census_rows_present"] = True

        header = payload[0]
        data = payload[1]
        notes.append(f"rows={len(payload) - 1}")

        bm = self.definition.benchmark
        if bm.variable in header:
            observed = float(data[header.index(bm.variable)])
            checks["census_benchmark_value_present"] = observed > 0
            notes.append(f"benchmark_{bm.variable}={observed:,.0f}")
            if bm.expected_value is not None:
                err = abs(observed - bm.expected_value) / bm.expected_value
                checks["census_benchmark"] = err <= bm.tolerance
                notes.append(f"expected={bm.expected_value}")
            else:
                checks["census_benchmark"] = True  # presence-based until key verification
                notes.append("expected_value unset; presence-based benchmark")
        else:
            checks["census_benchmark_value_present"] = False

        return ValidationResult(passed=all(checks.values()), checks=checks, notes=notes)

    def normalize_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> list[Path]:
        json_path = None
        for a in artifacts:
            if str(a.role) == DATA_JSON:
                json_path = run_root / a.relative_path
                break
        if json_path is None or not json_path.exists():
            return []

        with json_path.open() as f:
            payload = json.load(f)

        header = payload[0]
        rows = []
        for row in payload[1:]:
            rows.append({header[i]: row[i] for i in range(len(header))})
        df = pd.DataFrame(rows)
        out_dir = run_root / "normalized"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / "census_estimates.parquet"
        df.to_parquet(out_path, index=False)
        return [out_path]

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


def _load_definition(path: Path) -> CensusConfig:
    with path.open() as f:
        return CensusConfig.model_validate(yaml.safe_load(f))
