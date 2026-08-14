"""OECD Taxing Wages decomposition adapter (SDMX 2.1 REST dialect).

Fetches the OECD Tax Wages decomposition dataset
(DSD_TAX_WAGES_DECOMP@DF_TW_DECOMP) from the new dissemination service
at sdmx.oecd.org/public/rest. This is the dataset behind the OECD
"Tax wedge" statistics: marginal and average tax wedges, cash benefits,
and labour cost components by wage level (50-250% of average wage),
household type (single, one-earner married, two-earner), and year.

Unlike the legacy stats.oecd.org/SDMX-JSON v1 endpoint used by the
`oecd` adapter, this uses the SDMX 2.1 REST dialect:
  /public/rest/data/{agency},{flow},{version}/{key}?dimensionAtObservation=AllDimensions
with observations stored in a flat index keyed by dimension position.
"""

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

API_BASE = "https://sdmx.oecd.org/public/rest/data"
DEFINITION_PATH = Path(__file__).resolve().parents[3] / "config/oecd-tax-wages/tax-wedge.yaml"
_url_adapter = TypeAdapter(AnyHttpUrl)

DATA_JSON = "data_json"


class TaxWagesBenchmark(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref_area: str | None = None
    measure: str | None = None
    household_type: str | None = None
    income_principal: str | None = None
    time_period: str | None = None
    # Alternative shape: arbitrary dimension->code filters (SHA flow).
    filters: dict[str, str] | None = None
    expected_value: float | None = None
    tolerance: float = 0.01


class TaxWagesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = "oecd_tax_wages"
    agency: str
    flow: str
    version: str
    key: str
    dataset_title: str
    landing_page: AnyHttpUrl
    reference_year: int
    start_period: str
    output_name: str = "tax_wages"
    benchmark: TaxWagesBenchmark
    terms: str = "oecd_open_use"


class OECDTaxWagesAdapter(SourceAdapter):
    def __init__(
        self,
        *,
        definition: TaxWagesConfig | None = None,
        definition_path: Path | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        if definition is None:
            definition = _load_definition(definition_path or DEFINITION_PATH)
        self.definition = definition
        self.slug = definition.slug
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

    def _data_url(self) -> str:
        d = self.definition
        return (
            f"{API_BASE}/{d.agency},{d.flow},{d.version}/{d.key}"
            f"?startPeriod={d.start_period}"
            f"&dimensionAtObservation=AllDimensions&format=jsondata"
        )

    def discover(self, year: int | None = None) -> DiscoveredRelease:
        selected_year = year or self.definition.reference_year
        d = self.definition
        return DiscoveredRelease(
            survey=self.slug,
            year=selected_year,
            landing_page=d.landing_page,
            artifacts=[
                DiscoveredArtifact(
                    role=DATA_JSON,
                    url=_url_adapter.validate_python(self._data_url()),
                    filename=f"{d.flow.replace('@', '_')}_{selected_year}.json",
                    link_text=f"OECD {d.dataset_title} {selected_year}",
                )
            ],
            source_metadata={
                "record_unit": "country_year_wagelevel_observation",
                "dataset": d.flow,
                "dataset_title": d.dataset_title,
                "api": "OECD SDMX 2.1 REST (sdmx.oecd.org/public/rest)",
                "start_period": d.start_period,
                "benchmark_ref_area": d.benchmark.ref_area,
                "benchmark_measure": d.benchmark.measure,
                "no_registration_required": True,
                "terms": d.terms,
            },
        )

    def _parse(self, payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
        """Flatten an AllDimensions SDMX-JSON response into rows.

        Returns (rows, notes). Each observation key is a colon-joined index
        into the observation dimension value lists.
        """
        data = payload.get("data", payload)
        structures = data.get("structures", [])
        data_sets = data.get("dataSets", [])
        if not structures or not data_sets:
            return [], ["no structures or dataSets"]
        s = structures[0]
        obs_dims = s.get("dimensions", {}).get("observation", [])
        dim_ids = [d["id"] for d in obs_dims]
        code_lists = {d["id"]: [v["id"] for v in d.get("values", [])] for d in obs_dims}
        obs = data_sets[0].get("observations", {})
        rows: list[dict[str, Any]] = []
        for key, val in obs.items():
            parts = key.split(":")
            rec: dict[str, Any] = {}
            for dim_id, part in zip(dim_ids, parts, strict=True):
                codes = code_lists.get(dim_id, [])
                idx = int(part)
                rec[dim_id] = codes[idx] if idx < len(codes) else f"idx_{idx}"
            rec["value"] = val[0] if val else None
            rows.append(rec)
        return rows, [f"total_observations={len(rows)}"]

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
            payload = json.load(handle)

        rows, parse_notes = self._parse(payload)
        notes.extend(parse_notes)
        checks["oecd_tw_json_present"] = True
        checks["oecd_tw_observations_present"] = len(rows) > 0

        if rows:
            df = pd.DataFrame(rows)
            bm = self.definition.benchmark
            if bm.filters:
                mask = pd.Series(True, index=df.index)
                for column, code in bm.filters.items():
                    mask &= df[column] == code
                bm_rows = df[mask]
            else:
                bm_rows = df[
                    (df["REF_AREA"] == bm.ref_area)
                    & (df["MEASURE"] == bm.measure)
                    & (df["HOUSEHOLD_TYPE"] == bm.household_type)
                    & (df["INCOME_PRINCIPAL"] == bm.income_principal)
                    & (df["TIME_PERIOD"] == bm.time_period)
                ]
            checks["oecd_tw_benchmark_observation_present"] = len(bm_rows) >= 1
            if bm.expected_value is not None and len(bm_rows) >= 1:
                observed = float(bm_rows.iloc[0]["value"])
                checks["oecd_tw_benchmark_value_matches"] = (
                    abs(observed - bm.expected_value) <= bm.tolerance
                )
                notes.append(f"benchmark_observed={observed} expected={bm.expected_value}")
            elif bm.expected_value is None:
                checks["oecd_tw_benchmark_value_matches"] = True
                notes.append("benchmark_expected_value=null (presence check only)")
            else:
                checks["oecd_tw_benchmark_value_matches"] = False
        else:
            checks["oecd_tw_benchmark_observation_present"] = False
            checks["oecd_tw_benchmark_value_matches"] = False

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
            payload = json.load(handle)
        rows, _ = self._parse(payload)
        if not rows:
            return []
        df = pd.DataFrame(rows)
        out_dir = run_root / "normalized"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"{self.definition.output_name}.parquet"
        df.to_parquet(out_path, index=False)
        return [out_path]

    def download_client(self) -> httpx.Client:
        return self.client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


def _load_definition(path: Path) -> TaxWagesConfig:
    with path.open() as handle:
        return TaxWagesConfig.model_validate(yaml.safe_load(handle))


def _artifact_path(artifacts: list[StoredArtifact], role: str, run_root: Path) -> Path:
    matches = [a for a in artifacts if str(a.role) == role]
    if len(matches) != 1:
        raise ValueError(f"Expected one {role} artifact, found {len(matches)}")
    return run_root / matches[0].relative_path
