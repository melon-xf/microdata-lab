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

API_BASE = "https://stats.oecd.org/SDMX-JSON/data"
DEFINITION_PATH = Path(__file__).resolve().parents[3] / "config/oecd/qna.yaml"
_url_adapter = TypeAdapter(AnyHttpUrl)

DATA_JSON = "data_json"


class OECDBenchmark(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref_area: str
    transaction: str
    transformation: str
    frequency: str
    time_period: str
    expected_value: float | None = None
    tolerance: float = 0.01


class OECDDatasetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: str
    dataset_title: str
    dataset_url: AnyHttpUrl
    frequency: str
    landing_page: AnyHttpUrl
    reference_year: int
    time_range: dict[str, str]
    benchmark: OECDBenchmark


class OECDAdapter(SourceAdapter):
    slug = "oecd"

    def __init__(
        self,
        *,
        definition: OECDDatasetConfig | None = None,
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
        bm = self.definition.benchmark
        key = f"{bm.ref_area}.{bm.transaction}.{bm.transformation}.{bm.frequency}"
        url = f"{API_BASE}/{self.definition.dataset}/{key}/all"
        artifact = DiscoveredArtifact(
            role=DATA_JSON,
            url=_url_adapter.validate_python(url),
            filename=f"{self.definition.dataset}_{selected_year}.json",
            link_text=f"OECD {self.definition.dataset} {selected_year}",
            documentation=False,
        )
        return DiscoveredRelease(
            survey=self.slug,
            year=selected_year,
            landing_page=self.definition.landing_page,
            artifacts=[artifact],
            source_metadata={
                "record_unit": "macrodata_observation",
                "dataset": self.definition.dataset,
                "dataset_title": self.definition.dataset_title,
                "frequency": self.definition.frequency,
                "time_range": self.definition.time_range,
                "benchmark_ref_area": bm.ref_area,
                "benchmark_transaction": bm.transaction,
                "api": "OECD SDMX-JSON v1",
                "no_registration_required": True,
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

        data = response.get("data", {})
        structures = data.get("structures", [])
        datasets = data.get("dataSets", [])

        checks["oecd_response_has_structure"] = len(structures) >= 1
        checks["oecd_response_has_datasets"] = len(datasets) >= 1

        series_dims: list[dict[str, Any]] = []
        obs_dim_labels: list[str] = []
        if structures:
            s = structures[0]
            series_dims = s.get("dimensions", {}).get("series", [])
            obs_dims = s.get("dimensions", {}).get("observation", [])
            for od in obs_dims:
                obs_dim_labels = [v["id"] for v in od.get("values", [])]

        bm = self.definition.benchmark
        if datasets and series_dims:
            ds = datasets[0]
            series = ds.get("series", {})
            total_obs = sum(len(sd.get("observations", {})) for sd in series.values())
            checks["oecd_observations_present"] = total_obs > 0
            notes.append(f"total_observations={total_obs}")

            flat = _flatten_series(series, series_dims, obs_dim_labels)
            if flat:
                df = pd.DataFrame(flat)
                checks["oecd_dataframe_built"] = len(df) > 0
                time_range = self.definition.time_range
                start = time_range.get("start", "")
                end = time_range.get("end", "")
                in_range = df[(df["TIME_PERIOD"] >= start) & (df["TIME_PERIOD"] <= end)]
                checks["oecd_time_range_matches"] = len(in_range) > 0

                bm_obs = df[
                    (df["REF_AREA"] == bm.ref_area)
                    & (df["TRANSFORMATION"] == bm.transformation)
                    & (df["FREQ"] == bm.frequency)
                    & (df["TIME_PERIOD"] == bm.time_period)
                ]
                checks["oecd_benchmark_observation_present"] = len(bm_obs) > 0
                if bm.expected_value is not None and len(bm_obs) == 1:
                    observed = float(bm_obs.iloc[0]["value"])
                    checks["oecd_benchmark_value_matches"] = (
                        abs(observed - bm.expected_value) <= bm.tolerance
                    )
                    notes.append(f"benchmark_observed={observed} expected={bm.expected_value}")
                elif bm.expected_value is None:
                    checks["oecd_benchmark_value_matches"] = True
                    notes.append("benchmark_expected_value=null (presence check only)")
                else:
                    checks["oecd_benchmark_value_matches"] = False
            else:
                checks["oecd_dataframe_built"] = False
                checks["oecd_time_range_matches"] = False
                checks["oecd_benchmark_observation_present"] = False
                checks["oecd_benchmark_value_matches"] = False
        else:
            for key in (
                "oecd_observations_present",
                "oecd_dataframe_built",
                "oecd_time_range_matches",
                "oecd_benchmark_observation_present",
                "oecd_benchmark_value_matches",
            ):
                checks[key] = False

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

        data = response.get("data", {})
        structures = data.get("structures", [])
        datasets = data.get("dataSets", [])

        normalized = run_root / "normalized"
        normalized.mkdir(parents=True, exist_ok=True)

        if not structures or not datasets:
            return []

        s = structures[0]
        series_dims = s.get("dimensions", {}).get("series", [])
        obs_dims = s.get("dimensions", {}).get("observation", [])
        obs_dim_labels = [v["id"] for v in obs_dims[0].get("values", [])] if obs_dims else []

        flat = _flatten_series(datasets[0].get("series", {}), series_dims, obs_dim_labels)
        if not flat:
            return []

        df = pd.DataFrame(flat)
        output = normalized / f"{self.definition.dataset}.parquet"
        df.to_parquet(output, engine="pyarrow", compression="zstd")
        return [output]

    def download_client(self) -> httpx.Client:
        return self.client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()


def _load_definition(path: Path) -> OECDDatasetConfig:
    with path.open() as handle:
        return OECDDatasetConfig.model_validate(yaml.safe_load(handle))


def _flatten_series(
    series: dict[str, Any],
    series_dims: list[dict[str, Any]],
    obs_dim_labels: list[str],
) -> list[dict[str, Any]]:
    dim_labels: list[tuple[str, list[tuple[int, str]]]] = []
    for dim in series_dims:
        dim_id = dim["id"]
        values = [(i, v["id"]) for i, v in enumerate(dim.get("values", []))]
        dim_labels.append((dim_id, values))

    flat: list[dict[str, Any]] = []
    # Row values may be str (dimension codes) or float (observation value)
    for series_key, series_data in series.items():
        indices = [int(x) for x in series_key.split(":")]
        row_dims: dict[str, str] = {}
        for i, (dim_id, values) in enumerate(dim_labels):
            if i < len(indices):
                idx = indices[i]
                if 0 <= idx < len(values):
                    row_dims[dim_id] = values[idx][1]

        observations = series_data.get("observations", {})
        for time_idx, obs_value in observations.items():
            row: dict[str, Any] = dict(row_dims)
            row["TIME_PERIOD"] = (
                obs_dim_labels[int(time_idx)]
                if int(time_idx) < len(obs_dim_labels)
                else f"idx_{time_idx}"
            )
            row["value"] = float(obs_value[0]) if obs_value else None
            flat.append(row)
    return flat


def _artifact_path(artifacts: list[StoredArtifact], role: str, run_root: Path) -> Path:
    matches = [a for a in artifacts if str(a.role) == role]
    if len(matches) != 1:
        raise ValueError(f"Expected one {role} artifact, found {len(matches)}")
    return run_root / matches[0].relative_path
