from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import httpx
import pyarrow.parquet as pq
import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from microdata_lab.adapters.ipums import (
    BenchmarkDefinition,
    IPUMSAdapter,
    IPUMSSourceDefinition,
    _raise_for_status,
    load_ipums_definition,
)
from microdata_lab.models import DiscoveredRelease, StoredArtifact

_HTTP_URL = TypeAdapter(AnyHttpUrl)
_SAMPLE_HTML = """
<table>
<tr><th>Sample ID</th><th>Description</th></tr>
<tr><td>us2023a</td><td>2023 ACS</td></tr>
<tr><td>us2024a</td><td>2024 ACS</td></tr>
</table>
"""


def _definition() -> IPUMSSourceDefinition:
    return IPUMSSourceDefinition(
        slug="fixture_ipums",
        collection="usa",
        landing_page=_HTTP_URL.validate_python("https://samples.test/ids"),
        sample_page=_HTTP_URL.validate_python("https://samples.test/ids"),
        sample_id_pattern=r"^us(?P<year>\d{4})a$",
        minimum_year=2023,
        weight="PERWT",
        variables=["YEAR", "PERWT", "VALUE"],
        benchmark=BenchmarkDefinition(
            year=2024,
            kind="weighted_total",
            variable="PERWT",
            expected=3,
            relative_tolerance=0,
            source="https://official.test/benchmark",
        ),
    )


def _public_client() -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_SAMPLE_HTML, request=request)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_provider_error_detail_is_surfaced_and_email_is_redacted() -> None:
    request = httpx.Request("POST", "https://api.ipums.org/extracts")
    response = httpx.Response(
        400,
        json={
            "detail": [
                "Invalid variable name: NOPE",
                "Account user@example.com is not registered",
            ]
        },
        request=request,
    )

    with pytest.raises(RuntimeError) as captured:
        _raise_for_status(response)

    message = str(captured.value)
    assert "Invalid variable name: NOPE" in message
    assert "[REDACTED EMAIL]" in message
    assert "user@example.com" not in message


def test_official_ipums_definitions_load() -> None:
    assert load_ipums_definition("acs_pums").collection == "usa"
    cps = load_ipums_definition("cps_asec")
    assert cps.collection == "cps"
    assert cps.benchmark.universe_variable == "OFFPOVUNIV"
    assert cps.benchmark.universe_values == [1]
    assert cps.benchmark.threshold == 20
    atus = load_ipums_definition("atus")
    assert atus.collection == "atus"
    assert atus.time_use_variable_ids == {"BLS_LEIS": 5916, "BLS_PCARE": 5850}
    assert atus.benchmark.expected == 5.07


def test_discover_submits_polls_and_records_checksums() -> None:
    data = b"YEAR,PERWT,VALUE\n2024,1,2\n"
    requests: list[tuple[str, str]] = []
    submitted: dict[str, object] = {}

    def api_handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.method == "GET" and request.url.path == "/extracts":
            assert request.url.params["pageNumber"] == "1"
            assert request.url.params["pageSize"] == "100"
            assert "limit" not in request.url.params
            return httpx.Response(200, json=[], request=request)
        if request.method == "POST" and request.url.path == "/extracts":
            submitted.update(json.loads(request.content))
            return httpx.Response(200, json={"number": 7, "status": "queued"}, request=request)
        if request.url.path == "/extracts/7":
            return httpx.Response(
                200,
                json={
                    "number": 7,
                    "status": "completed",
                    "downloadLinks": {
                        "data": {
                            "url": "https://api.ipums.org/downloads/data.csv.gz",
                            "bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest(),
                        },
                        "basicCodebook": {
                            "url": "https://api.ipums.org/downloads/codebook.cbk",
                            "bytes": 4,
                            "sha256": hashlib.sha256(b"book").hexdigest(),
                        },
                    },
                },
                request=request,
            )
        raise AssertionError(f"Unexpected API request: {request.method} {request.url}")

    with (
        httpx.Client(
            base_url="https://api.ipums.org",
            transport=httpx.MockTransport(api_handler),
            headers={"Authorization": "test-key"},
        ) as api_client,
        _public_client() as public_client,
    ):
        adapter = IPUMSAdapter(
            "fixture_ipums",
            definition=_definition(),
            api_client=api_client,
            public_client=public_client,
            poll_interval=0,
        )
        release = adapter.discover()

    assert release.year == 2024
    assert release.source_metadata["extract_number"] == 7
    assert submitted["samples"] == {"us2024a": {}}
    assert "collection" not in submitted
    assert "version" not in submitted
    assert str(submitted["description"]).startswith("microdata-lab:fixture_ipums:2024:")
    assert {str(artifact.role) for artifact in release.artifacts} == {"data", "basicCodebook"}
    data_artifact = next(artifact for artifact in release.artifacts if artifact.role == "data")
    assert data_artifact.expected_sha256 == hashlib.sha256(data).hexdigest()
    assert ("POST", "/extracts") in requests
    assert ("GET", "/extracts/7") in requests


def test_validation_and_streaming_parquet_normalization(tmp_path: Path) -> None:
    raw = b"YEAR,PERWT,VALUE\n2024,1,10\n2024,2,20\n"
    data_path = tmp_path / "artifacts" / "data" / "fixture.csv.gz"
    data_path.parent.mkdir(parents=True)
    with gzip.open(data_path, "wb") as output:
        output.write(raw)
    codebook_path = tmp_path / "artifacts" / "basicCodebook" / "fixture.cbk"
    codebook_path.parent.mkdir(parents=True)
    codebook_path.write_text("book")
    artifacts = [
        StoredArtifact(
            role="data",
            source_url=_HTTP_URL.validate_python("https://api.ipums.org/data.csv.gz"),
            filename="fixture.csv.gz",
            relative_path=str(data_path.relative_to(tmp_path)),
            sha256=hashlib.sha256(data_path.read_bytes()).hexdigest(),
            bytes=data_path.stat().st_size,
        ),
        StoredArtifact(
            role="basicCodebook",
            source_url=_HTTP_URL.validate_python("https://api.ipums.org/codebook.cbk"),
            filename="fixture.cbk",
            relative_path=str(codebook_path.relative_to(tmp_path)),
            sha256=hashlib.sha256(codebook_path.read_bytes()).hexdigest(),
            bytes=codebook_path.stat().st_size,
            documentation=True,
        ),
    ]
    release = DiscoveredRelease(
        survey="fixture_ipums",
        year=2024,
        landing_page=_HTTP_URL.validate_python("https://samples.test/ids"),
        artifacts=[],
        source_metadata={"extract_number": 7, "extract_fingerprint": "abc"},
    )
    with (
        httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))) as api,
        _public_client() as public,
    ):
        adapter = IPUMSAdapter(
            "fixture_ipums",
            definition=_definition(),
            api_client=api,
            public_client=public,
        )
        validation = adapter.validate_release(tmp_path, release, artifacts)
        normalized = adapter.normalize_release(tmp_path, release, artifacts)

    assert validation.passed is True
    assert validation.checks["official_benchmark"] is True
    assert len(normalized) == 1
    table = pq.read_table(normalized[0])
    assert table.num_rows == 2
    assert table.column_names == ["YEAR", "PERWT", "VALUE"]


def test_weighted_count_benchmark_applies_official_universe(tmp_path: Path) -> None:
    raw = b"YEAR,PERWT,POVERTY,OFFPOVUNIV\n2025,100,0,0\n2025,2,10,1\n2025,3,21,1\n"
    data_path = tmp_path / "artifacts" / "data" / "cps.csv.gz"
    data_path.parent.mkdir(parents=True)
    with gzip.open(data_path, "wb") as output:
        output.write(raw)
    codebook_path = tmp_path / "artifacts" / "basicCodebook" / "cps.cbk"
    codebook_path.parent.mkdir(parents=True)
    codebook_path.write_text("book")
    artifacts = [
        StoredArtifact(
            role="data",
            source_url=_HTTP_URL.validate_python("https://api.ipums.org/cps.csv.gz"),
            filename="cps.csv.gz",
            relative_path=str(data_path.relative_to(tmp_path)),
            sha256=hashlib.sha256(data_path.read_bytes()).hexdigest(),
            bytes=data_path.stat().st_size,
        ),
        StoredArtifact(
            role="basicCodebook",
            source_url=_HTTP_URL.validate_python("https://api.ipums.org/cps.cbk"),
            filename="cps.cbk",
            relative_path=str(codebook_path.relative_to(tmp_path)),
            sha256=hashlib.sha256(codebook_path.read_bytes()).hexdigest(),
            bytes=codebook_path.stat().st_size,
            documentation=True,
        ),
    ]
    definition = _definition().model_copy(
        update={
            "variables": ["YEAR", "PERWT", "POVERTY", "OFFPOVUNIV"],
            "benchmark": BenchmarkDefinition(
                year=2025,
                kind="weighted_count_below",
                variable="POVERTY",
                weight="PERWT",
                threshold=20,
                universe_variable="OFFPOVUNIV",
                universe_values=[1],
                expected=2,
                relative_tolerance=0,
                source="https://official.test/poverty",
            ),
        }
    )
    release = DiscoveredRelease(
        survey="fixture_ipums",
        year=2025,
        landing_page=_HTTP_URL.validate_python("https://samples.test/ids"),
        artifacts=[],
        source_metadata={"extract_number": 8, "extract_fingerprint": "def"},
    )
    with (
        httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))) as api,
        _public_client() as public,
    ):
        adapter = IPUMSAdapter(
            "fixture_ipums",
            definition=definition,
            api_client=api,
            public_client=public,
        )
        validation = adapter.validate_release(tmp_path, release, artifacts)

    assert validation.passed is True
    assert validation.checks["ipums_benchmark_universe_nonempty"] is True
    assert validation.checks["official_benchmark"] is True
    assert "observed=2" in validation.notes[-1]
