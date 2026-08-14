from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
import pandas as pd
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
import yaml
from pydantic import AnyHttpUrl, BaseModel, Field, TypeAdapter, model_validator
from selectolax.parser import HTMLParser

from microdata_lab.adapters.base import SourceAdapter
from microdata_lab.models import (
    DiscoveredArtifact,
    DiscoveredRelease,
    StoredArtifact,
    ValidationResult,
)
from microdata_lab.secrets import load_runtime_environment, require_secret

_API_ROOT = "https://api.ipums.org"
_HTTP_URL = TypeAdapter(AnyHttpUrl)
_TERMINAL_FAILURES = {"canceled", "failed"}
_READY_STATUSES = {"completed", "produced"}
_EMAIL_ADDRESS = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")


class BenchmarkDefinition(BaseModel):
    year: int
    kind: Literal["weighted_total", "weighted_count_below", "weighted_mean_hours"]
    variable: str
    weight: str | None = None
    threshold: float | None = None
    universe_variable: str | None = None
    universe_values: list[float] = Field(default_factory=list)
    expected: float
    relative_tolerance: float | None = None
    absolute_tolerance: float | None = None
    source: str


class IPUMSSourceDefinition(BaseModel):
    slug: str
    collection: str
    landing_page: AnyHttpUrl
    sample_page: AnyHttpUrl
    sample_id_pattern: str
    minimum_year: int
    latest_lag: int = 0
    data_format: Literal["csv", "fixed_width"] = "csv"
    weight: str
    variables: list[str]
    time_use_variables: list[str] = Field(default_factory=list)
    time_use_variable_ids: dict[str, int] = Field(default_factory=dict)
    sample_members: dict[str, bool] | None = None
    benchmark: BenchmarkDefinition

    @model_validator(mode="after")
    def validate_time_use_variable_ids(self) -> IPUMSSourceDefinition:
        if set(self.time_use_variable_ids) != set(self.time_use_variables):
            raise ValueError("time_use_variable_ids must map every configured time-use variable")
        return self


class IPUMSAdapter(SourceAdapter):
    """Deterministic API-v2 adapter for IPUMS microdata collections."""

    def __init__(
        self,
        slug: str,
        *,
        definition: IPUMSSourceDefinition | None = None,
        api_key: str | None = None,
        api_client: httpx.Client | None = None,
        public_client: httpx.Client | None = None,
        poll_interval: float = 30.0,
        poll_timeout: float = 3600.0,
    ) -> None:
        self.definition = definition or load_ipums_definition(slug)
        self.slug = self.definition.slug
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout
        self._sample_cache: dict[int, str] | None = None
        self._owns_api_client = api_client is None
        self._owns_public_client = public_client is None
        if api_client is None:
            load_runtime_environment()
            key = api_key or require_secret("IPUMS_API_KEY")
            api_client = httpx.Client(
                base_url=_API_ROOT,
                follow_redirects=True,
                timeout=httpx.Timeout(connect=30.0, read=180.0, write=60.0, pool=30.0),
                transport=httpx.HTTPTransport(retries=3),
                headers={
                    "Authorization": key,
                    "Content-Type": "application/json",
                    "User-Agent": "microdata-lab/0.1",
                },
            )
        self.api_client = api_client
        self.public_client = public_client or httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(60.0),
            transport=httpx.HTTPTransport(retries=3),
            headers={"User-Agent": "microdata-lab/0.1"},
        )

    def available_years(self) -> list[int]:
        return sorted(self._samples())

    def discover(self, year: int | None = None) -> DiscoveredRelease:
        samples = self._samples()
        years = sorted(samples)
        if not years:
            raise ValueError(f"No sample IDs discovered for {self.slug}")
        if year is None:
            selected_index = len(years) - 1 - self.definition.latest_lag
            if selected_index < 0:
                raise ValueError(f"No benchmark-ready sample is available for {self.slug}")
            year = years[selected_index]
        if year not in samples:
            raise ValueError(f"{self.slug} year {year} is not present on the official sample page")

        extract_definition, fingerprint = self._extract_definition(year, samples[year])
        description = extract_definition["description"]
        status = self._find_extract(description)
        if status is None:
            response = self.api_client.post(
                "/extracts",
                params={"collection": self.definition.collection, "version": 2},
                json=extract_definition,
            )
            _raise_for_status(response)
            status = _json_object(response)
        status = self._wait_for_extract(status)
        artifacts = self._artifacts_from_status(status)
        if not artifacts:
            raise RuntimeError(f"IPUMS extract {status.get('number')} completed without downloads")

        return DiscoveredRelease(
            survey=self.slug,
            year=year,
            landing_page=self.definition.landing_page,
            artifacts=artifacts,
            source_metadata={
                "provider": "IPUMS",
                "api_version": 2,
                "collection": self.definition.collection,
                "sample": samples[year],
                "time_use_variable_ids": self.definition.time_use_variable_ids,
                "extract_number": status.get("number"),
                "extract_fingerprint": fingerprint,
                "extract_definition": extract_definition,
                "benchmark": self.definition.benchmark.model_dump(mode="json"),
            },
        )

    def download_client(self) -> httpx.Client:
        return self.api_client

    def validate_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> ValidationResult:
        data_files = [
            run_root / artifact.relative_path
            for artifact in artifacts
            if str(artifact.role) == "data"
        ]
        codebooks = [artifact for artifact in artifacts if str(artifact.role) == "basicCodebook"]
        checks: dict[str, bool] = {
            "ipums_data_present": len(data_files) == 1,
            "ipums_codebook_present": len(codebooks) == 1,
            "ipums_extract_number_recorded": bool(release.source_metadata.get("extract_number")),
            "ipums_extract_fingerprint_recorded": bool(
                release.source_metadata.get("extract_fingerprint")
            ),
        }
        notes: list[str] = []
        if len(data_files) != 1:
            return _validation(checks, ["Expected exactly one IPUMS data artifact"])

        data_path = data_files[0]
        header = pd.read_csv(data_path, nrows=5)
        columns = {column.upper(): column for column in header.columns}
        requested = {
            *self.definition.variables,
            *self.definition.time_use_variables,
        }
        missing = sorted(variable for variable in requested if variable.upper() not in columns)
        checks["ipums_requested_variables_present"] = not missing
        if missing:
            notes.append(f"Missing requested IPUMS variables: {', '.join(missing)}")

        benchmark = self.definition.benchmark
        needed = {"YEAR", self.definition.weight, benchmark.variable}
        if benchmark.universe_variable:
            needed.add(benchmark.universe_variable)
        actual_needed = [columns[name.upper()] for name in needed if name.upper() in columns]
        if len(actual_needed) != len(needed):
            checks["ipums_validation_variables_present"] = False
            return _validation(checks, notes)

        weighted_total = 0.0
        benchmark_numerator = 0.0
        benchmark_denominator = 0.0
        benchmark_universe_weight = 0.0
        row_count = 0
        years: set[int] = set()
        weight_name = columns[(benchmark.weight or self.definition.weight).upper()]
        variable_name = columns[benchmark.variable.upper()]
        year_name = columns["YEAR"]
        universe_name = (
            columns[benchmark.universe_variable.upper()]
            if benchmark.universe_variable is not None
            else None
        )
        for chunk in pd.read_csv(data_path, usecols=actual_needed, chunksize=250_000):
            row_count += len(chunk)
            weights = pd.to_numeric(chunk[weight_name], errors="coerce")
            values = pd.to_numeric(chunk[variable_name], errors="coerce")
            weighted_total += float(weights.fillna(0).sum())
            years.update(
                int(value)
                for value in pd.to_numeric(chunk[year_name], errors="coerce").dropna().unique()
            )
            valid = weights.notna() & values.notna() & (weights > 0)
            if universe_name is not None:
                universe = pd.to_numeric(chunk[universe_name], errors="coerce")
                valid &= universe.isin(benchmark.universe_values)
                benchmark_universe_weight += float(weights[valid].sum())
            if benchmark.kind == "weighted_count_below":
                if benchmark.threshold is None:
                    raise ValueError("weighted_count_below benchmark requires a threshold")
                benchmark_numerator += float(weights[valid & (values < benchmark.threshold)].sum())
            elif benchmark.kind == "weighted_mean_hours":
                benchmark_numerator += float((weights[valid] * values[valid]).sum())
                benchmark_denominator += float(weights[valid].sum())

        checks.update(
            {
                "ipums_rows_nonempty": row_count > 0,
                "ipums_weight_positive": weighted_total > 0,
                "ipums_year_matches_release": years == {release.year},
            }
        )
        if universe_name is not None:
            checks["ipums_benchmark_universe_nonempty"] = benchmark_universe_weight > 0
        if release.year == benchmark.year:
            observed = weighted_total
            if benchmark.kind == "weighted_count_below":
                observed = benchmark_numerator
            elif benchmark.kind == "weighted_mean_hours":
                observed = benchmark_numerator / benchmark_denominator / 60.0
            if benchmark.absolute_tolerance is not None:
                passed = abs(observed - benchmark.expected) <= benchmark.absolute_tolerance
            else:
                tolerance = benchmark.relative_tolerance or 0.0
                passed = abs(observed - benchmark.expected) / benchmark.expected <= tolerance
            checks["official_benchmark"] = passed
            notes.append(
                f"Official benchmark observed={observed:.6g}, expected={benchmark.expected:.6g}; "
                f"source={benchmark.source}"
            )
        else:
            checks["official_benchmark_pipeline_year"] = True
            notes.append(
                f"Structural validation only for {release.year}; the adapter's official benchmark "
                f"is release year {benchmark.year}."
            )
        return _validation(checks, notes)

    def normalize_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> list[Path]:
        matches = [
            run_root / artifact.relative_path
            for artifact in artifacts
            if str(artifact.role) == "data"
        ]
        if len(matches) != 1:
            raise ValueError(f"Expected one IPUMS data file, found {len(matches)}")
        destination = run_root / "normalized" / f"{self.slug}-{release.year}.parquet"
        destination.parent.mkdir(parents=True, exist_ok=True)
        with pa.input_stream(str(matches[0]), compression="detect") as source:
            reader = pacsv.open_csv(source)
            metadata = {
                b"microdata_lab.survey": self.slug.encode(),
                b"microdata_lab.year": str(release.year).encode(),
                b"microdata_lab.extract_fingerprint": str(
                    release.source_metadata.get("extract_fingerprint", "")
                ).encode(),
            }
            schema = reader.schema.with_metadata(metadata)
            with pq.ParquetWriter(destination, schema, compression="zstd") as writer:
                for batch in reader:
                    writer.write_batch(batch.replace_schema_metadata(metadata))
        return [destination]

    def close(self) -> None:
        if self._owns_api_client:
            self.api_client.close()
        if self._owns_public_client:
            self.public_client.close()

    def _samples(self) -> dict[int, str]:
        if self._sample_cache is not None:
            return self._sample_cache
        response = self.public_client.get(str(self.definition.sample_page))
        response.raise_for_status()
        pattern = re.compile(self.definition.sample_id_pattern)
        samples: dict[int, str] = {}
        for row in HTMLParser(response.text).css("table tr"):
            cells = [cell.text(strip=True) for cell in row.css("th, td")]
            if not cells:
                continue
            match = pattern.fullmatch(cells[0])
            if not match:
                continue
            year = int(match.group("year"))
            if year >= self.definition.minimum_year:
                samples[year] = cells[0]
        self._sample_cache = samples
        return samples

    def _extract_definition(self, year: int, sample: str) -> tuple[dict[str, Any], str]:
        core: dict[str, Any] = {
            "dataStructure": {"rectangular": {"on": "P"}},
            "dataFormat": self.definition.data_format,
            "caseSelectWho": "individuals",
            "samples": {sample: {}},
            "variables": {variable: {} for variable in self.definition.variables},
        }
        if self.definition.time_use_variables:
            core["timeUseVariables"] = {
                variable: {} for variable in self.definition.time_use_variables
            }
        if self.definition.sample_members is not None:
            core["sampleMembers"] = self.definition.sample_members
        fingerprint_payload = {
            "api_version": 2,
            "collection": self.definition.collection,
            "extract_definition": core,
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        core["description"] = f"microdata-lab:{self.slug}:{year}:{fingerprint[:16]}"
        return core, fingerprint

    def _find_extract(self, description: str) -> dict[str, Any] | None:
        response = self.api_client.get(
            "/extracts",
            params={
                "collection": self.definition.collection,
                "version": 2,
                "pageNumber": 1,
                "pageSize": 100,
            },
        )
        _raise_for_status(response)
        payload = response.json()
        records: list[Any]
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict):
            listing = payload.get("data", payload.get("extracts", []))
            if not isinstance(listing, list):
                raise RuntimeError("IPUMS extract listing did not contain a list")
            records = listing
        else:
            raise RuntimeError("IPUMS extract listing returned an unexpected response")
        for record in records:
            if not isinstance(record, dict):
                continue
            definition = record.get("extractDefinition", {})
            if isinstance(definition, dict) and definition.get("description") == description:
                return {str(key): value for key, value in record.items()}
        return None

    def _wait_for_extract(self, initial: dict[str, Any]) -> dict[str, Any]:
        status = initial
        number = status.get("number")
        if number is None:
            raise RuntimeError("IPUMS extract response did not include an extract number")
        deadline = time.monotonic() + self.poll_timeout
        while str(status.get("status", "")).lower() not in _READY_STATUSES:
            state = str(status.get("status", "")).lower()
            if state in _TERMINAL_FAILURES:
                raise RuntimeError(f"IPUMS extract {number} ended with status {state}")
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"IPUMS extract {number} did not complete within {self.poll_timeout}s"
                )
            time.sleep(self.poll_interval)
            response = self.api_client.get(
                f"/extracts/{number}",
                params={"collection": self.definition.collection, "version": 2},
            )
            _raise_for_status(response)
            status = _json_object(response)
        return status

    def _artifacts_from_status(self, status: dict[str, Any]) -> list[DiscoveredArtifact]:
        links = status.get("downloadLinks", {})
        artifacts: list[DiscoveredArtifact] = []
        for role, link in sorted(links.items()):
            if not isinstance(link, dict) or not link.get("url"):
                continue
            url = str(link["url"])
            filename = Path(urlparse(url).path).name
            artifacts.append(
                DiscoveredArtifact(
                    role=role,
                    url=_HTTP_URL.validate_python(url),
                    link_text=role,
                    filename=filename,
                    documentation=role == "basicCodebook",
                    expected_sha256=link.get("sha256"),
                    expected_bytes=link.get("bytes"),
                )
            )
        return artifacts


def load_ipums_definition(slug: str) -> IPUMSSourceDefinition:
    path = Path(__file__).resolve().parents[3] / "config" / "ipums" / f"{slug}.yaml"
    if not path.is_file():
        raise ValueError(f"Unknown IPUMS source definition: {slug}")
    return IPUMSSourceDefinition.model_validate(yaml.safe_load(path.read_text()))


def _json_object(response: httpx.Response) -> dict[str, Any]:
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("IPUMS API returned a non-object response")
    return payload


def _raise_for_status(response: httpx.Response) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        detail = ""
        try:
            payload = response.json()
            if isinstance(payload, dict):
                provider_detail = payload.get("detail", payload.get("error", ""))
                detail = json.dumps(provider_detail, ensure_ascii=True)
        except ValueError:
            detail = ""
        detail = _EMAIL_ADDRESS.sub("[REDACTED EMAIL]", detail)[:1000]
        suffix = f": {detail}" if detail else ""
        raise RuntimeError(f"IPUMS API returned HTTP {response.status_code}{suffix}") from error


def _validation(checks: dict[str, bool], notes: list[str]) -> ValidationResult:
    failed = [name for name, passed in checks.items() if not passed]
    if failed and not notes:
        notes.append(f"Failed IPUMS checks: {', '.join(failed)}")
    return ValidationResult(passed=all(checks.values()), checks=checks, notes=notes)
