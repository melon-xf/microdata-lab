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

API_BASE = "https://rplumber.ilo.org"
DEFINITION_PATH = Path(__file__).resolve().parents[3] / "config/ilo/unemployment-rate.yaml"
_url_adapter = TypeAdapter(AnyHttpUrl)

DATA_JSON = "data_json"


class IloBenchmark(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref_area: str
    sex: str = "SEX_T"
    classif1: str | None = None
    expected_value: float | None = None
    tolerance: float = 0.01
    description: str = ""


class IloConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    indicator_id: str
    indicator_code: str
    indicator_title: str
    indicator_url: AnyHttpUrl
    landing_page: AnyHttpUrl
    reference_year: int
    benchmark: IloBenchmark
    terms: str = "ilo_non_commercial_attribution"
    record_unit: str = "country_year_observation"


class IloAdapter(SourceAdapter):
    slug = "ilo"

    def __init__(
        self,
        *,
        definition: IloConfig | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.definition = definition or _load_definition(DEFINITION_PATH)
        self._client = client

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
            f"{API_BASE}/data/indicator"
            f"?id={self.definition.indicator_id}"
            f"&ref_area={self.definition.benchmark.ref_area}"
            f"&timefrom={selected_year}&timeto={selected_year}"
            f"&format=.json"
        )
        return DiscoveredRelease(
            survey=self.slug,
            year=selected_year,
            landing_page=self.definition.landing_page,
            artifacts=[
                DiscoveredArtifact(
                    role=DATA_JSON,
                    url=_url_adapter.validate_python(url),
                    filename=f"ilo_{self.definition.indicator_code}_{selected_year}.json",
                    link_text=f"ILO ILOSTAT {self.definition.indicator_title}",
                )
            ],
            source_metadata={
                "record_unit": self.definition.record_unit,
                "indicator": self.definition.indicator_id,
                "indicator_title": self.definition.indicator_title,
                "api": "ILO ILOSTAT API (rplumber.ilo.org)",
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
            checks["ilo_json_present"] = False
            return ValidationResult(passed=False, checks=checks, notes=notes)
        checks["ilo_json_present"] = True

        with json_path.open() as f:
            payload = json.load(f)
        rows = payload if isinstance(payload, list) else payload.get("value", [])
        checks["ilo_observations_present"] = len(rows) > 0
        notes.append(f"total_observations={len(rows)}")

        bm = self.definition.benchmark
        if bm.expected_value is not None:
            matched = [
                r
                for r in rows
                if r.get("ref_area") == bm.ref_area
                and r.get("sex") == bm.sex
                and r.get("classif1") == bm.classif1
                and str(r.get("time")) == str(release.year)
            ]
            if matched:
                observed = float(matched[0]["obs_value"])
                err = abs(observed - bm.expected_value) / bm.expected_value
                checks["ilo_benchmark"] = err <= bm.tolerance
                notes.append(
                    f"benchmark_{bm.ref_area}_{release.year}={observed:.4f} "
                    f"expected={bm.expected_value}"
                )
            else:
                checks["ilo_benchmark"] = False
                notes.append(
                    "benchmark row not found for "
                    f"{bm.ref_area}/{bm.sex}/{bm.classif1}/{release.year}"
                )

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
        rows = payload if isinstance(payload, list) else payload.get("value", [])

        df = pd.DataFrame(rows)
        out_dir = run_root / "normalized"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / "ilo_ilostat.parquet"
        df.to_parquet(out_path, index=False)
        return [out_path]

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


def _load_definition(path: Path) -> IloConfig:
    with path.open() as f:
        return IloConfig.model_validate(yaml.safe_load(f))
