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

API_BASE = "https://api.stlouisfed.org/fred"
DEFINITION_PATH = Path(__file__).resolve().parents[3] / "config/fred/real-gdp.yaml"
_url_adapter = TypeAdapter(AnyHttpUrl)

DATA_JSON = "data_json"


class FredBenchmark(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: str  # observation date, e.g. "2025-10-01"
    expected_value: float
    tolerance: float = 0.001
    description: str = ""


class FredConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_id: str
    series_title: str
    series_url: AnyHttpUrl
    landing_page: AnyHttpUrl
    reference_year: int
    benchmark: FredBenchmark
    terms: str = "fred_open_terms"
    record_unit: str = "quarterly_observation"
    credential: str = "FRED_API_KEY"


class FredAdapter(SourceAdapter):
    slug = "fred"

    def __init__(
        self,
        *,
        definition: FredConfig | None = None,
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
        url = (
            f"{API_BASE}/series/observations"
            f"?series_id={self.definition.series_id}"
            f"&api_key={self.api_key}"
            f"&file_type=json"
            f"&observation_start={selected_year}-01-01"
        )
        return DiscoveredRelease(
            survey=self.slug,
            year=selected_year,
            landing_page=self.definition.landing_page,
            artifacts=[
                DiscoveredArtifact(
                    role=DATA_JSON,
                    url=_url_adapter.validate_python(url),
                    filename=f"fred_{self.definition.series_id}_{selected_year}.json",
                    link_text=f"FRED {self.definition.series_title}",
                )
            ],
            source_metadata={
                "record_unit": self.definition.record_unit,
                "series_id": self.definition.series_id,
                "series_title": self.definition.series_title,
                "api": "FRED API v1",
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
            checks["fred_json_present"] = False
            return ValidationResult(passed=False, checks=checks, notes=notes)
        checks["fred_json_present"] = True

        with json_path.open() as f:
            payload = json.load(f)
        if "error_code" in payload:
            checks["fred_request_succeeded"] = False
            notes.append(f"fred_error={payload.get('error_message', '')}")
            return ValidationResult(passed=False, checks=checks, notes=notes)
        checks["fred_request_succeeded"] = True

        obs = payload.get("observations", [])
        checks["fred_observations_present"] = len(obs) > 0
        notes.append(f"total_observations={len(obs)}")

        bm = self.definition.benchmark
        matched = [o for o in obs if o.get("date") == bm.period]
        if matched:
            observed = float(matched[0]["value"])
            err = abs(observed - bm.expected_value) / bm.expected_value
            checks["fred_benchmark"] = err <= bm.tolerance
            notes.append(f"benchmark_{bm.period}={observed:.3f} expected={bm.expected_value}")
        else:
            checks["fred_benchmark"] = False
            notes.append(f"benchmark observation not found for {bm.period}")

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

        rows = []
        for o in payload.get("observations", []):
            rows.append(
                {
                    "series_id": self.definition.series_id,
                    "date": o.get("date"),
                    "value": o.get("value"),
                    "realtime_start": o.get("realtime_start"),
                    "realtime_end": o.get("realtime_end"),
                }
            )
        df = pd.DataFrame(rows).sort_values("date")
        out_dir = run_root / "normalized"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / "fred_observations.parquet"
        df.to_parquet(out_path, index=False)
        return [out_path]

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


def _load_definition(path: Path) -> FredConfig:
    with path.open() as f:
        return FredConfig.model_validate(yaml.safe_load(f))
