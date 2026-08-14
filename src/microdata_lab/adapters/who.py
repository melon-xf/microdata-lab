from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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

API_BASE = "https://ghoapi.azureedge.net/api"
DEFINITION_PATH = Path(__file__).resolve().parents[3] / "config/who/life-expectancy.yaml"
_url_adapter = TypeAdapter(AnyHttpUrl)

DATA_JSON = "data_json"


class WhoBenchmark(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country: str
    sex: str = "SEX_BTSX"
    expected_value: float | None = None
    tolerance: float = 0.01
    description: str = ""


class WhoConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    indicator_code: str
    indicator_title: str
    indicator_url: AnyHttpUrl
    landing_page: AnyHttpUrl
    reference_year: int
    benchmark: WhoBenchmark
    terms: str = "cc_by_4_0"
    record_unit: str = "country_year_observation"


class WhoAdapter(SourceAdapter):
    slug = "who"

    def __init__(
        self,
        *,
        definition: WhoConfig | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.definition = definition or _load_definition(DEFINITION_PATH)
        self._client = client

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                follow_redirects=True,
                timeout=180,
                headers={"User-Agent": "microdata-lab/1.0"},
            )
        return self._client

    def available_years(self) -> list[int]:
        return [self.definition.reference_year]

    def discover(self, year: int | None = None) -> DiscoveredRelease:
        selected_year = year or self.definition.reference_year
        url = f"{API_BASE}/{self.definition.indicator_code}"
        return DiscoveredRelease(
            survey=self.slug,
            year=selected_year,
            landing_page=self.definition.landing_page,
            artifacts=[
                DiscoveredArtifact(
                    role=DATA_JSON,
                    url=_url_adapter.validate_python(url),
                    filename=f"who_{self.definition.indicator_code}_{selected_year}.json",
                    link_text=f"WHO GHO {self.definition.indicator_title}",
                )
            ],
            source_metadata={
                "record_unit": self.definition.record_unit,
                "indicator": self.definition.indicator_code,
                "indicator_title": self.definition.indicator_title,
                "api": "WHO GHO API (ghoapi.azureedge.net)",
                "no_registration_required": True,
                "terms": self.definition.terms,
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
            checks["who_json_present"] = False
            return ValidationResult(passed=False, checks=checks, notes=notes)
        checks["who_json_present"] = True

        with json_path.open() as f:
            payload = json.load(f)
        values = payload.get("value", [])
        checks["who_observations_present"] = len(values) > 0
        notes.append(f"total_observations={len(values)}")

        bm = self.definition.benchmark
        if bm.expected_value is not None:
            matched = [
                v
                for v in values
                if v.get("SpatialDim") == bm.country
                and v.get("Dim1") == bm.sex
                and v.get("TimeDim") == release.year
            ]
            if matched:
                observed = float(matched[0]["NumericValue"])
                err = abs(observed - bm.expected_value) / bm.expected_value
                checks["who_benchmark"] = err <= bm.tolerance
                notes.append(
                    f"benchmark_{bm.country}_{release.year}={observed:.4f} "
                    f"expected={bm.expected_value}"
                )
            else:
                checks["who_benchmark"] = False
                notes.append(f"benchmark row not found for {bm.country}/{bm.sex}/{release.year}")

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

        rows: list[dict[str, Any]] = []
        for v in payload.get("value", []):
            rows.append(
                {
                    "country_code": v.get("SpatialDim"),
                    "year": v.get("TimeDim"),
                    "sex": v.get("Dim1"),
                    "value": v.get("NumericValue"),
                    "low": v.get("Low"),
                    "high": v.get("High"),
                    "std_err": v.get("StdErr"),
                }
            )
        df = pd.DataFrame(rows)
        out_dir = run_root / "normalized"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / "who_gho.parquet"
        df.to_parquet(out_path, index=False)
        return [out_path]

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


def _load_definition(path: Path) -> WhoConfig:
    with path.open() as f:
        return WhoConfig.model_validate(yaml.safe_load(f))
