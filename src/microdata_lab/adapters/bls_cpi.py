from __future__ import annotations

import json
from pathlib import Path

import httpx
import pandas as pd
import yaml
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, TypeAdapter

from microdata_lab.adapters.base import SourceAdapter
from microdata_lab.bls import build_bls_client
from microdata_lab.models import (
    DiscoveredArtifact,
    DiscoveredRelease,
    StoredArtifact,
    ValidationResult,
)

API_BASE = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
DEFINITION_PATH = Path(__file__).resolve().parents[3] / "config/bls/cpi-u.yaml"
_url_adapter = TypeAdapter(AnyHttpUrl)

DATA_JSON = "data_json"


class BlsBenchmark(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: str  # e.g. "2024-12"
    expected_value: float
    tolerance: float = 0.001
    description: str = ""


class BlsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_id: str
    series_title: str
    series_url: AnyHttpUrl
    landing_page: AnyHttpUrl
    reference_year: int
    benchmark: BlsBenchmark
    terms: str = "us_federal_public_domain"
    record_unit: str = "monthly_index_observation"


class BlsAdapter(SourceAdapter):
    slug = "bls_cpi"

    def __init__(
        self,
        *,
        definition: BlsConfig | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.definition = definition or _load_definition(DEFINITION_PATH)
        self._client = client

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = build_bls_client()
        return self._client

    def download_client(self) -> httpx.Client:
        """Return the BLS-only client with the protected identifying User-Agent."""
        return self.client

    def available_years(self) -> list[int]:
        return [self.definition.reference_year]

    def discover(self, year: int | None = None) -> DiscoveredRelease:
        selected_year = year or self.definition.reference_year
        payload = {
            "seriesid": [self.definition.series_id],
            "startyear": str(selected_year),
            "endyear": str(selected_year),
            "catalog": False,
        }
        return DiscoveredRelease(
            survey=self.slug,
            year=selected_year,
            landing_page=self.definition.landing_page,
            artifacts=[
                DiscoveredArtifact(
                    role=DATA_JSON,
                    url=_url_adapter.validate_python(API_BASE),
                    filename=f"bls_{self.definition.series_id}_{selected_year}.json",
                    link_text=f"BLS {self.definition.series_title}",
                    request_payload=payload,
                )
            ],
            source_metadata={
                "record_unit": self.definition.record_unit,
                "series_id": self.definition.series_id,
                "series_title": self.definition.series_title,
                "api": "BLS Public Data API v2",
                "identifying_user_agent": True,
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
            checks["bls_json_present"] = False
            return ValidationResult(passed=False, checks=checks, notes=notes)
        checks["bls_json_present"] = True

        with json_path.open() as f:
            payload = json.load(f)
        status = payload.get("status")
        checks["bls_request_succeeded"] = status == "REQUEST_SUCCEEDED"
        notes.append(f"bls_status={status}")

        series = payload.get("Results", {}).get("series", [])
        checks["bls_series_present"] = len(series) > 0
        if not series:
            return ValidationResult(passed=all(checks.values()), checks=checks, notes=notes)

        points = series[0].get("data", [])
        checks["bls_points_present"] = len(points) > 0
        notes.append(f"total_points={len(points)}")

        bm = self.definition.benchmark
        target = bm.period.split("-")
        matched = [
            p
            for p in points
            if p.get("year") == target[0] and p.get("period") == f"M{int(target[1]):02d}"
        ]
        if matched:
            observed = float(matched[0]["value"])
            err = abs(observed - bm.expected_value) / bm.expected_value
            checks["bls_benchmark"] = err <= bm.tolerance
            notes.append(f"benchmark_{bm.period}={observed:.3f} expected={bm.expected_value}")
        else:
            checks["bls_benchmark"] = False
            notes.append(f"benchmark point not found for {bm.period}")

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
        series = payload.get("Results", {}).get("series", [])
        if not series:
            return []

        rows = []
        for p in series[0].get("data", []):
            rows.append(
                {
                    "series_id": self.definition.series_id,
                    "year": int(p["year"]),
                    "period": p["period"],
                    "period_name": p.get("periodName"),
                    "value": float(p["value"]),
                    "footnotes": " | ".join(f.get("text", "") for f in p.get("footnotes", [])),
                }
            )
        df = pd.DataFrame(rows).sort_values(["year", "period"])
        out_dir = run_root / "normalized"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / "bls_cpi_u.parquet"
        df.to_parquet(out_path, index=False)
        return [out_path]

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


def _load_definition(path: Path) -> BlsConfig:
    with path.open() as f:
        return BlsConfig.model_validate(yaml.safe_load(f))
