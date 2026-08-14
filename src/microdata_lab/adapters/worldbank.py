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

API_BASE = "https://api.worldbank.org/v2"
DEFINITION_PATH = Path(__file__).resolve().parents[3] / "config/worldbank/gdp.yaml"
_url_adapter = TypeAdapter(AnyHttpUrl)

DATA_JSON = "data_json"


class WorldBankBenchmark(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country: str
    expected_value: float | None = None
    tolerance: float = 0.01


class WorldBankConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    indicator: str
    indicator_title: str
    indicator_url: AnyHttpUrl
    landing_page: AnyHttpUrl
    reference_year: int
    benchmark: WorldBankBenchmark
    terms: str = "cc_by_4_0"


class WorldBankAdapter(SourceAdapter):
    slug = "worldbank"

    def __init__(
        self,
        *,
        definition: WorldBankConfig | None = None,
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
            f"{API_BASE}/country/all/indicator/{self.definition.indicator}"
            f"?format=json&date={selected_year}&per_page=1000"
        )
        return DiscoveredRelease(
            survey=self.slug,
            year=selected_year,
            landing_page=self.definition.landing_page,
            artifacts=[
                DiscoveredArtifact(
                    role=DATA_JSON,
                    url=_url_adapter.validate_python(url),
                    filename=f"wb_{self.definition.indicator}_{selected_year}.json",
                    link_text=f"World Bank {self.definition.indicator_title} {selected_year}",
                )
            ],
            source_metadata={
                "record_unit": "macrodata_observation",
                "indicator": self.definition.indicator,
                "indicator_title": self.definition.indicator_title,
                "api": "World Bank API v2",
                "no_registration_required": True,
                "terms": self.definition.terms,
                "redistribution_note": (
                    "World Development Indicators is licensed CC BY 4.0; "
                    "published aggregates require World Bank attribution."
                ),
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

        json_path = _artifact_path(artifacts, DATA_JSON, run_root)
        with json_path.open() as handle:
            response = json.load(handle)

        checks["wb_response_has_data_page"] = isinstance(response, list) and len(response) >= 2
        if not checks["wb_response_has_data_page"]:
            return ValidationResult(passed=False, checks=checks, notes=notes)

        metadata = response[0]
        data = response[1]
        checks["wb_observations_present"] = len(data) > 0
        notes.append(f"total_observations={len(data)}")
        notes.append(f"pages={metadata.get('pages', '?')}")

        df = pd.DataFrame(data)
        checks["wb_dataframe_built"] = len(df) > 0

        bm = self.definition.benchmark
        bm_obs = df[df["countryiso3code"] == bm.country]
        checks["wb_benchmark_observation_present"] = len(bm_obs) >= 1

        if bm.expected_value is not None and len(bm_obs) >= 1:
            observed = float(bm_obs.iloc[0]["value"])
            checks["wb_benchmark_value_matches"] = abs(observed - bm.expected_value) <= bm.tolerance
            notes.append(f"benchmark_observed={observed} expected={bm.expected_value}")
        elif bm.expected_value is None:
            checks["wb_benchmark_value_matches"] = True
            notes.append("benchmark_expected_value=null (presence check only)")
        else:
            checks["wb_benchmark_value_matches"] = False

        checks["wb_has_indicator_id"] = "indicator" in df.columns
        checks["wb_has_country_iso3"] = "countryiso3code" in df.columns
        checks["wb_has_value_column"] = "value" in df.columns

        return ValidationResult(passed=all(checks.values()), checks=checks, notes=notes)

    def normalize_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> list[Path]:
        del release
        json_path = _artifact_path(artifacts, DATA_JSON, run_root)
        with json_path.open() as handle:
            response = json.load(handle)

        if not isinstance(response, list) or len(response) < 2:
            return []

        data = response[1]
        if not data:
            return []

        df = pd.DataFrame(data)
        # Flatten nested dicts
        if "indicator" in df.columns:
            df["indicator_id"] = df["indicator"].apply(
                lambda x: x.get("id") if isinstance(x, dict) else None
            )
            df["indicator_name"] = df["indicator"].apply(
                lambda x: x.get("value") if isinstance(x, dict) else None
            )
            df = df.drop(columns=["indicator"])
        if "country" in df.columns:
            df["country_id"] = df["country"].apply(
                lambda x: x.get("id") if isinstance(x, dict) else None
            )
            df["country_name"] = df["country"].apply(
                lambda x: x.get("value") if isinstance(x, dict) else None
            )
            df = df.drop(columns=["country"])

        normalized = run_root / "normalized"
        normalized.mkdir(parents=True, exist_ok=True)
        output = normalized / f"wb_{self.definition.indicator}.parquet"
        df.to_parquet(output, engine="pyarrow", compression="zstd")
        return [output]

    def download_client(self) -> httpx.Client:
        return self.client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()


def _load_definition(path: Path) -> WorldBankConfig:
    with path.open() as handle:
        return WorldBankConfig.model_validate(yaml.safe_load(handle))


def _artifact_path(artifacts: list[StoredArtifact], role: str, run_root: Path) -> Path:
    matches = [a for a in artifacts if str(a.role) == role]
    if len(matches) != 1:
        raise ValueError(f"Expected one {role} artifact, found {len(matches)}")
    return run_root / matches[0].relative_path
