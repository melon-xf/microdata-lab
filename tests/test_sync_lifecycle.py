from __future__ import annotations

import io
import json
import zipfile
from collections import Counter
from pathlib import Path

import httpx
import pytest
from filelock import FileLock
from pydantic import AnyHttpUrl, TypeAdapter

from microdata_lab.adapters.base import SourceAdapter
from microdata_lab.models import (
    ArtifactRole,
    DiscoveredArtifact,
    DiscoveredRelease,
    StoredArtifact,
    ValidationResult,
)
from microdata_lab.storage import ReleaseValidationError, sync_release, validate_current_release

_HTTP_URL = TypeAdapter(AnyHttpUrl)
_FILENAMES = {
    ArtifactRole.FULL_DATA_STATA: "full.zip",
    ArtifactRole.REPLICATE_WEIGHTS_STATA: "weights.zip",
    ArtifactRole.SUMMARY_EXTRACT_CSV: "summary-csv.zip",
    ArtifactRole.SUMMARY_EXTRACT_STATA: "summary-stata.zip",
    ArtifactRole.CODEBOOK: "codebook.txt",
    ArtifactRole.STANDARD_ERROR_DOCUMENTATION: "standard-errors.pdf",
    ArtifactRole.CHANGES: "changes.txt",
    ArtifactRole.VARIABLE_DEFINITIONS: "variables.txt",
}
_MEMBERS = {
    ArtifactRole.FULL_DATA_STATA: "full.dta",
    ArtifactRole.REPLICATE_WEIGHTS_STATA: "weights.dta",
    ArtifactRole.SUMMARY_EXTRACT_CSV: "summary.csv",
    ArtifactRole.SUMMARY_EXTRACT_STATA: "summary.dta",
}


def _archive(member: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as bundle:
        bundle.writestr(member, b"fixture")
    return output.getvalue()


def _release() -> DiscoveredRelease:
    artifacts = [
        DiscoveredArtifact(
            role=role,
            url=_HTTP_URL.validate_python(f"https://official.test/{filename}"),
            link_text=role.value,
            filename=filename,
        )
        for role, filename in _FILENAMES.items()
    ]
    return DiscoveredRelease(
        survey="fixture",
        year=2024,
        landing_page=_HTTP_URL.validate_python("https://official.test/releases"),
        artifacts=artifacts,
    )


def _payloads(*, malformed_full_data: bool = False) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    for role, filename in _FILENAMES.items():
        if role in _MEMBERS:
            is_malformed = malformed_full_data and role == ArtifactRole.FULL_DATA_STATA
            member = "wrong.txt" if is_malformed else _MEMBERS[role]
            payloads[f"/{filename}"] = _archive(member)
        else:
            payloads[f"/{filename}"] = b"fixture document"
    return payloads


class FixtureAdapter(SourceAdapter):
    slug = "fixture"

    def discover(self, year: int | None = None) -> DiscoveredRelease:
        return _release()

    def validate_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> ValidationResult:
        return ValidationResult(passed=True, checks={"fixture_hook": True})

    def normalize_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> list[Path]:
        destination = run_root / "normalized" / "fixture.txt"
        destination.parent.mkdir(parents=True)
        destination.write_text("normalized\n")
        return [destination]


def test_sync_promotes_then_skips_unchanged_remote(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "microdata_lab.storage.build_document_sidecars", lambda *_args, **_kwargs: []
    )
    payloads = _payloads()
    requests: Counter[str] = Counter()

    def handler(request: httpx.Request) -> httpx.Response:
        requests[request.method] += 1
        path = request.url.path
        headers = {"etag": f'"{Path(path).name}-v1"'}
        if request.method == "HEAD":
            return httpx.Response(200, headers=headers, request=request)
        return httpx.Response(200, content=payloads[path], headers=headers, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first = sync_release(_release(), tmp_path, client=client)
        second = sync_release(_release(), tmp_path, client=client)

    assert first.changed is True
    assert second.changed is False
    assert first.release_path == second.release_path
    assert requests["GET"] == len(ArtifactRole)
    assert requests["HEAD"] == len(ArtifactRole)
    assert list((tmp_path / "incoming").iterdir()) == []
    assert (first.release_path / "manifest.json").is_file()
    assert (tmp_path / "current" / "fixture.json").is_file()


def test_failed_release_moves_to_quarantine(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "microdata_lab.storage.build_document_sidecars", lambda *_args, **_kwargs: []
    )
    payloads = _payloads(malformed_full_data=True)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=payloads[request.url.path],
            headers={"etag": '"fixture-v1"'},
            request=request,
        )

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ReleaseValidationError),
    ):
        sync_release(_release(), tmp_path, client=client)

    quarantined = list((tmp_path / "quarantine").iterdir())
    assert len(quarantined) == 1
    assert (quarantined[0] / "artifacts" / ArtifactRole.FULL_DATA_STATA.value).is_dir()
    assert list((tmp_path / "releases").iterdir()) == []
    assert not (tmp_path / "current" / "fixture.json").exists()


def test_changed_remote_bytes_create_a_new_immutable_revision(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "microdata_lab.storage.build_document_sidecars", lambda *_args, **_kwargs: []
    )
    payloads = _payloads()
    version = 1

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        headers = {"etag": f'"{Path(path).name}-v{version}"'}
        if request.method == "HEAD":
            return httpx.Response(200, headers=headers, request=request)
        payload = payloads[path]
        if version == 2 and path == "/changes.txt":
            payload += b" revised"
        return httpx.Response(200, content=payload, headers=headers, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first = sync_release(_release(), tmp_path, client=client)
        version = 2
        second = sync_release(_release(), tmp_path, client=client)

    assert first.release_path != second.release_path
    assert first.release_path.is_dir()
    assert second.release_path.is_dir()
    assert len(list((tmp_path / "releases" / "fixture" / "2024").iterdir())) == 2
    pointer = json.loads((tmp_path / "current" / "fixture.json").read_text())
    assert Path(pointer["release_path"]) == second.release_path


def test_sync_rejects_an_overlapping_source_run(tmp_path: Path) -> None:
    lock_path = tmp_path / "locks" / "fixture.lock"
    lock_path.parent.mkdir(parents=True)
    with FileLock(str(lock_path)), pytest.raises(RuntimeError, match="already running"):
        sync_release(_release(), tmp_path)


def test_adapter_validation_and_normalization_are_recorded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "microdata_lab.storage.build_document_sidecars", lambda *_args, **_kwargs: []
    )
    payloads = _payloads()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payloads[request.url.path], request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = sync_release(_release(), tmp_path, adapter=FixtureAdapter(), client=client)

    assert result.manifest.validation.checks["fixture_hook"] is True
    assert len(result.manifest.normalized_assets) == 1
    asset = result.manifest.normalized_assets[0]
    assert asset.relative_path == "normalized/fixture.txt"
    assert (result.release_path / asset.relative_path).read_text() == "normalized\n"


def test_transient_download_failure_is_retried(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "microdata_lab.storage.build_document_sidecars", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr("microdata_lab.storage.time.sleep", lambda _seconds: None)
    payloads = _payloads()
    attempts: Counter[str] = Counter()

    def handler(request: httpx.Request) -> httpx.Response:
        attempts[request.url.path] += 1
        if request.url.path == "/full.zip" and attempts[request.url.path] == 1:
            return httpx.Response(
                503,
                headers={"retry-after": "0"},
                request=request,
            )
        return httpx.Response(200, content=payloads[request.url.path], request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = sync_release(_release(), tmp_path, client=client)

    assert result.changed is True
    assert attempts["/full.zip"] == 2


def test_revalidation_writes_an_external_log_without_mutating_release(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "microdata_lab.storage.build_document_sidecars", lambda *_args, **_kwargs: []
    )
    payloads = _payloads()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payloads[request.url.path], request=request)

    adapter = FixtureAdapter()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = sync_release(_release(), tmp_path, adapter=adapter, client=client)
    manifest_path = result.release_path / "manifest.json"
    original = manifest_path.read_bytes()

    manifest, release_path = validate_current_release(tmp_path, "fixture", adapter=adapter)

    assert manifest.validation.passed is True
    assert release_path == result.release_path
    assert manifest_path.read_bytes() == original
    assert len(list((tmp_path / "logs" / "validation").glob("fixture-*.json"))) == 1
