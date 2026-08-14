from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import yaml
from pydantic import AnyHttpUrl, BaseModel, TypeAdapter

from microdata_lab.adapters.base import SourceAdapter
from microdata_lab.models import (
    DiscoveredArtifact,
    DiscoveredRelease,
    StoredArtifact,
    ValidationResult,
)

_url_adapter = TypeAdapter(AnyHttpUrl)


class EurostatBenchmark(BaseModel):
    geo: str
    na_item: str
    unit: str
    time: str
    expected_value: float
    tolerance: float
    description: str = ""


class EurostatConfig(BaseModel):
    dataset: str
    dataset_title: str
    dataset_url: str
    landing_page: str
    filters: dict[str, str]
    benchmark: EurostatBenchmark
    terms: str = "cc_by_4_0"


class EurostatAdapter(SourceAdapter):
    slug = "eurostat"

    def __init__(self) -> None:
        self.client = httpx.Client(
            follow_redirects=True,
            timeout=60,
            headers={"User-Agent": "microdata-lab/1.0"},
        )
        config_path = Path(__file__).resolve().parents[3] / "config" / "eurostat" / "gdp.yaml"
        with config_path.open() as f:
            self.definition = EurostatConfig.model_validate(yaml.safe_load(f))

    def discover(self, year: int | None = None) -> DiscoveredRelease:
        yr = year or 2023
        return DiscoveredRelease(
            survey="eurostat",
            year=yr,
            landing_page=_url_adapter.validate_strings(self.definition.landing_page),
            artifacts=[
                DiscoveredArtifact(
                    role="data_json",
                    url=_url_adapter.validate_strings(f"{self.definition.dataset_url}"),
                    link_text=f"Eurostat {self.definition.dataset} {yr}",
                    filename=f"{self.definition.dataset}_{yr}.json",
                ),
            ],
            source_metadata={"dataset": self.definition.dataset, "terms": self.definition.terms},
        )

    def validate_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> ValidationResult:
        checks: dict[str, bool] = {}
        notes: list[str] = []

        # Load the downloaded JSON
        json_path = None
        for a in artifacts:
            if str(a.role) == "data_json":
                json_path = run_root / a.relative_path
                break
        if json_path is None or not json_path.exists():
            checks["eurostat_json_present"] = False
            return ValidationResult(passed=False, checks=checks, notes=notes)

        checks["eurostat_json_present"] = True
        with json_path.open() as f:
            payload = json.load(f)

        values = payload.get("value", {})
        checks["eurostat_observations_present"] = len(values) > 0
        notes.append(f"total_observations={len(values)}")

        # Verify benchmark
        if values:
            dims = payload.get("dimension", {})
            dim_order = list(dims.keys())
            size = payload.get("size", [])

            bm = self.definition.benchmark
            # Build reverse index maps: index -> code for each dimension
            dim_indices: dict[str, dict[int, str]] = {}
            for dim_id in dim_order:
                dim_data = dims[dim_id]
                index_list = dim_data.get("category", {}).get("index", {})
                dim_indices[dim_id] = {v: k for k, v in index_list.items()}

            # Find the flat index for the benchmark observation
            indices = []
            for dim_id in dim_order:
                dim_data = dims[dim_id]
                category = dim_data.get("category", {})
                index_list = category.get("index", {})
                label_list = category.get("label", {})

                # Check benchmark fields first, then filters
                filter_key = None
                if hasattr(bm, dim_id):
                    filter_key = getattr(bm, dim_id)
                if filter_key is None and dim_id in self.definition.filters:
                    # For filters with multiple values (comma-separated),
                    # use the first value for benchmark lookup
                    raw = self.definition.filters[dim_id]
                    filter_key = raw.split(",")[0] if raw else None

                if filter_key and filter_key in index_list:
                    indices.append(index_list[filter_key])
                elif filter_key:
                    # Try to find a matching label
                    found = False
                    for code, idx in index_list.items():
                        if code == filter_key or label_list.get(code) == filter_key:
                            indices.append(idx)
                            found = True
                            break
                    if not found:
                        indices.append(0)
                else:
                    indices.append(0)

            # Compute flat index: index[0]*prod(size[1:]) + index[1]*prod(size[2:]) + ...
            flat_idx = 0
            for i, idx in enumerate(indices):
                stride = 1
                for j in range(i + 1, len(size)):
                    stride *= size[j]
                flat_idx += idx * stride

            observed = values.get(str(flat_idx))
            checks["eurostat_benchmark_observation_present"] = observed is not None
            if observed is not None:
                observed = float(observed)
                diff = abs(observed - bm.expected_value)
                checks["eurostat_benchmark_value_matches"] = diff <= bm.tolerance
                notes.append(
                    f"benchmark_observed={observed} expected={bm.expected_value} diff={diff}"
                )
            else:
                checks["eurostat_benchmark_value_matches"] = False

        return ValidationResult(passed=all(checks.values()), checks=checks, notes=notes)

    def normalize_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> list[Path]:
        del release
        json_path = None
        for a in artifacts:
            if str(a.role) == "data_json":
                json_path = run_root / a.relative_path
                break
        if json_path is None or not json_path.exists():
            return []

        with json_path.open() as f:
            payload = json.load(f)

        dims = payload.get("dimension", {})
        dim_order = list(dims.keys())
        values = payload.get("value", {})
        size = payload.get("size", [])

        if not values:
            return []

        # Flatten to rows
        flat: list[dict[str, Any]] = []
        for key, val in values.items():
            flat_idx = int(key)
            row: dict[str, Any] = {}
            # Compute multi-dimensional indices
            remaining = flat_idx
            indices = []
            for i in range(len(dim_order)):
                stride = 1
                for j in range(i + 1, len(dim_order)):
                    stride *= size[j]
                indices.append(remaining // stride)
                remaining = remaining % stride

            for i, dim_id in enumerate(dim_order):
                dim_data = dims[dim_id]
                category = dim_data.get("category", {})
                index_map = category.get("index", {})
                label_map = category.get("label", {})
                idx = indices[i]
                # Find the code for this index
                code = None
                for c, ci in index_map.items():
                    if ci == idx:
                        code = c
                        break
                row[dim_id] = code or str(idx)
                row[f"{dim_id}_label"] = label_map.get(code, code or "")
            row["value"] = float(val)
            flat.append(row)

        normalized = run_root / "normalized"
        normalized.mkdir(parents=True, exist_ok=True)
        output = normalized / f"{self.definition.dataset}.parquet"
        df = pd.DataFrame(flat)
        df.to_parquet(output, engine="pyarrow", compression="zstd")
        return [output]

    def download_client(self) -> httpx.Client:
        return self.client

    def close(self) -> None:
        self.client.close()
