from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import time
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import httpx
import pyarrow.parquet as pq
from filelock import FileLock, Timeout

from microdata_lab.config import initialize_data_root
from microdata_lab.docs import build_document_sidecars
from microdata_lab.integrity import release_digest as calculate_release_digest
from microdata_lab.models import (
    RELEASE_SCHEMA_VERSION,
    ArtifactRole,
    DiscoveredArtifact,
    DiscoveredRelease,
    NormalizedAsset,
    ReleaseManifest,
    StoredArtifact,
    ValidationResult,
)

if TYPE_CHECKING:
    from microdata_lab.adapters.base import SourceAdapter

ProgressCallback = Callable[[str], None]
_TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}
_MAX_DOWNLOAD_ATTEMPTS = 4


class UnsafeArchiveError(ValueError):
    pass


class ReleaseValidationError(ValueError):
    pass


class SyncResult:
    def __init__(self, manifest: ReleaseManifest, release_path: Path, changed: bool) -> None:
        self.manifest = manifest
        self.release_path = release_path
        self.changed = changed


def safe_extract_zip(archive: Path, destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    extracted: list[Path] = []
    with zipfile.ZipFile(archive) as bundle:
        bad_member = bundle.testzip()
        if bad_member is not None:
            raise UnsafeArchiveError(f"Corrupt member in {archive.name}: {bad_member}")
        for info in bundle.infolist():
            member = Path(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if member.is_absolute() or ".." in member.parts or stat.S_ISLNK(mode):
                raise UnsafeArchiveError(f"Unsafe archive member: {info.filename}")
            target = (root / member).resolve()
            if target != root and root not in target.parents:
                raise UnsafeArchiveError(f"Archive member escapes destination: {info.filename}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            extracted.append(target)
    return sorted(extracted)


def sync_release(
    release: DiscoveredRelease,
    data_root: Path,
    *,
    adapter: SourceAdapter | None = None,
    client: httpx.Client | None = None,
    progress: ProgressCallback | None = None,
) -> SyncResult:
    initialize_data_root(data_root)
    lock = FileLock(str(data_root / "locks" / f"{release.survey}.lock"))
    try:
        with lock.acquire(timeout=0):
            return _sync_release_unlocked(
                release,
                data_root,
                adapter=adapter,
                client=client,
                progress=progress,
            )
    except Timeout as error:
        raise RuntimeError(
            f"Another {release.survey} synchronization is already running"
        ) from error


def _sync_release_unlocked(
    release: DiscoveredRelease,
    data_root: Path,
    *,
    adapter: SourceAdapter | None = None,
    client: httpx.Client | None = None,
    progress: ProgressCallback | None = None,
) -> SyncResult:
    initialize_data_root(data_root)
    report = progress or (lambda _: None)
    run_timestamp = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    run_name = f"{release.survey}-{release.year}-{run_timestamp}-{uuid4().hex[:8]}"
    run_root = data_root / "incoming" / run_name
    run_root.mkdir(parents=True)
    owns_client = client is None
    active_client = client or httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(connect=30.0, read=180.0, write=60.0, pool=30.0),
        transport=httpx.HTTPTransport(retries=3),
        headers={"User-Agent": "microdata-lab/0.1"},
    )
    try:
        existing = _current_if_remote_unchanged(active_client, release, data_root)
        if existing is not None:
            _remove_incoming_run(run_root, data_root / "incoming")
            report("Official artifacts unchanged; using current validated release")
            return existing
        stored: list[StoredArtifact] = []
        for artifact in release.artifacts:
            report(f"Downloading {artifact.role}: {artifact.filename}")
            stored.append(_download_artifact(active_client, artifact, run_root))
        validation = validate_release(run_root, stored, survey=release.survey)
        if adapter is not None:
            source_validation = adapter.validate_release(run_root, release, stored)
            validation = _merge_validation(validation, source_validation)
        if not validation.passed:
            raise ReleaseValidationError("; ".join(validation.notes))

        report("Building documentation sidecars")
        build_document_sidecars(run_root, stored)
        normalized_assets: list[NormalizedAsset] = []
        if adapter is not None:
            report("Normalizing analysis-ready files")
            normalized_assets = [
                _normalized_asset(run_root, path)
                for path in adapter.normalize_release(run_root, release, stored)
            ]
        release_digest = calculate_release_digest(stored)
        release_id = f"{release.survey}-{release.year}-{release_digest[:12]}"
        manifest = ReleaseManifest(
            survey=release.survey,
            year=release.year,
            release_id=release_id,
            landing_page=release.landing_page,
            discovered_at=release.discovered_at,
            release_sha256=release_digest,
            artifacts=stored,
            normalized_assets=normalized_assets,
            validation=validation,
            source_metadata=release.source_metadata,
        )
        _write_json_atomic(run_root / "manifest.json", json.loads(manifest.model_dump_json()))
        _write_json_atomic(run_root / "validation.json", validation.model_dump(mode="json"))

        destination = data_root / "releases" / release.survey / str(release.year) / release_digest
        destination.parent.mkdir(parents=True, exist_ok=True)
        changed = not destination.exists()
        if changed:
            os.replace(run_root, destination)
        else:
            _remove_incoming_run(run_root, data_root / "incoming")

        _write_json_atomic(
            data_root / "current" / f"{release.survey}.json",
            {
                "survey": release.survey,
                "year": release.year,
                "release_id": release_id,
                "release_sha256": release_digest,
                "release_path": str(destination),
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )
        report("Release promoted" if changed else "Release already current")
        return SyncResult(manifest=manifest, release_path=destination, changed=changed)
    except Exception:
        if run_root.exists():
            quarantine = data_root / "quarantine" / run_name
            quarantine.parent.mkdir(parents=True, exist_ok=True)
            os.replace(run_root, quarantine)
        raise
    finally:
        if owns_client:
            active_client.close()


def _current_if_remote_unchanged(
    client: httpx.Client,
    release: DiscoveredRelease,
    data_root: Path,
) -> SyncResult | None:
    pointer_path = data_root / "current" / f"{release.survey}.json"
    if not pointer_path.is_file():
        return None
    try:
        pointer = json.loads(pointer_path.read_text())
        if int(pointer["year"]) != release.year:
            return None
        release_path = Path(pointer["release_path"]).resolve()
        expected_root = (data_root / "releases" / release.survey).resolve()
        if release_path == expected_root or expected_root not in release_path.parents:
            return None
        manifest = ReleaseManifest.model_validate_json((release_path / "manifest.json").read_text())
    except (KeyError, OSError, ValueError):
        return None
    if manifest.schema_version != RELEASE_SCHEMA_VERSION:
        return None

    stored_by_role = {artifact.role: artifact for artifact in manifest.artifacts}
    if set(stored_by_role) != {artifact.role for artifact in release.artifacts}:
        return None

    for discovered in release.artifacts:
        stored = stored_by_role[discovered.role]
        if str(stored.source_url) != str(discovered.url):
            return None
        # POST artifacts have no cacheable GET/HEAD surface; re-download to verify.
        if discovered.request_payload:
            return None
        try:
            response = client.head(str(discovered.url))
            response.raise_for_status()
        except httpx.HTTPError:
            return None
        remote_etag = response.headers.get("etag")
        remote_modified = response.headers.get("last-modified")
        remote_length = response.headers.get("content-length")
        if stored.etag and remote_etag:
            if stored.etag != remote_etag:
                return None
            continue
        if stored.upstream_last_modified and remote_modified and remote_length:
            if stored.upstream_last_modified != remote_modified or stored.bytes != int(
                remote_length
            ):
                return None
            continue
        return None

    return SyncResult(manifest=manifest, release_path=release_path, changed=False)


def validate_release(
    run_root: Path,
    artifacts: list[StoredArtifact],
    *,
    survey: str | None = None,
    year: int | None = None,
) -> ValidationResult:
    by_role = {artifact.role: artifact for artifact in artifacts}
    checks: dict[str, bool] = {
        "artifact_roles_unique": len(by_role) == len(artifacts),
        "all_files_nonempty": all(artifact.bytes > 0 for artifact in artifacts),
    }
    if survey == "scf":
        checks["all_required_roles"] = set(by_role) == set(ArtifactRole)
    expected_suffixes = {
        ArtifactRole.FULL_DATA_STATA: ".dta",
        ArtifactRole.REPLICATE_WEIGHTS_STATA: ".dta",
        ArtifactRole.SUMMARY_EXTRACT_STATA: ".dta",
        ArtifactRole.SUMMARY_EXTRACT_CSV: ".csv",
    }
    for role, suffix in expected_suffixes.items():
        artifact = by_role.get(role)
        if artifact is not None:
            checks[f"{role.value}_contains_{suffix[1:]}"] = any(
                path.lower().endswith(suffix) for path in artifact.extracted_files
            )
    for artifact in artifacts:
        checks[f"sha256_{artifact.role}"] = len(artifact.sha256) == 64
        checks[f"exists_{artifact.role}"] = (run_root / artifact.relative_path).is_file()

    notes: list[str] = []
    failed = [name for name, passed in checks.items() if not passed]
    if failed and not notes:
        notes.append(f"Failed release checks: {', '.join(failed)}")
    return ValidationResult(
        passed=not failed,
        checks=checks,
        notes=notes,
    )


def validate_current_release(
    data_root: Path,
    survey: str,
    *,
    adapter: SourceAdapter | None = None,
) -> tuple[ReleaseManifest, Path]:
    """Re-run current validators without fetching or modifying raw artifacts."""
    pointer_path = data_root / "current" / f"{survey}.json"
    pointer = json.loads(pointer_path.read_text())
    release_path = Path(pointer["release_path"]).resolve()
    expected_root = (data_root / "releases" / survey).resolve()
    if release_path == expected_root or expected_root not in release_path.parents:
        raise ValueError(f"Current release path is outside the expected root: {release_path}")

    manifest_path = release_path / "manifest.json"
    manifest = ReleaseManifest.model_validate_json(manifest_path.read_text())
    validation = validate_release(
        release_path,
        manifest.artifacts,
        survey=survey,
        year=manifest.year,
    )
    if adapter is not None:
        discovered = DiscoveredRelease(
            survey=manifest.survey,
            year=manifest.year,
            landing_page=manifest.landing_page,
            artifacts=[
                DiscoveredArtifact(
                    role=artifact.role,
                    url=artifact.source_url,
                    link_text=artifact.filename,
                    filename=artifact.filename,
                )
                for artifact in manifest.artifacts
            ],
            discovered_at=manifest.discovered_at,
            source_metadata=manifest.source_metadata,
        )
        validation = _merge_validation(
            validation,
            adapter.validate_release(release_path, discovered, manifest.artifacts),
        )
    updated = manifest.model_copy(update={"validation": validation})
    checked_at = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    _write_json_atomic(
        data_root
        / "logs"
        / "validation"
        / f"{survey}-{manifest.release_sha256[:12]}-{checked_at}.json",
        {
            "survey": survey,
            "release_id": manifest.release_id,
            "release_sha256": manifest.release_sha256,
            "checked_at": datetime.now(UTC).isoformat(),
            "validation": validation.model_dump(mode="json"),
        },
    )
    return updated, release_path


def _download_artifact(
    client: httpx.Client, artifact: DiscoveredArtifact, run_root: Path
) -> StoredArtifact:
    role_root = run_root / "artifacts" / str(artifact.role)
    role_root.mkdir(parents=True, exist_ok=True)
    destination = role_root / artifact.filename
    temporary = destination.with_suffix(destination.suffix + ".part")
    content_type: str | None = None
    for attempt in range(1, _MAX_DOWNLOAD_ATTEMPTS + 1):
        digest = hashlib.sha256()
        size = 0
        etag = last_modified = None
        try:
            if artifact.request_payload:
                with client.stream(
                    "POST",
                    str(artifact.url),
                    json=artifact.request_payload,
                ) as response:
                    if response.status_code in _TRANSIENT_HTTP_STATUS:
                        if attempt == _MAX_DOWNLOAD_ATTEMPTS:
                            response.raise_for_status()
                        _wait_before_retry(response.headers.get("retry-after"), attempt)
                        continue
                    response.raise_for_status()
                    with temporary.open("wb") as output:
                        for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                            if not chunk:
                                continue
                            output.write(chunk)
                            digest.update(chunk)
                            size += len(chunk)
                    content_length = response.headers.get("content-length")
                    if (
                        content_length
                        and not response.headers.get("content-encoding")
                        and size != int(content_length)
                    ):
                        raise httpx.ReadError(
                            f"Expected {content_length} bytes but received {size}",
                            request=response.request,
                        )
                    etag = response.headers.get("etag")
                    last_modified = response.headers.get("last-modified")
                    content_type = response.headers.get("content-type")
            else:
                with client.stream("GET", str(artifact.url)) as response:
                    if response.status_code in _TRANSIENT_HTTP_STATUS:
                        if attempt == _MAX_DOWNLOAD_ATTEMPTS:
                            response.raise_for_status()
                        _wait_before_retry(response.headers.get("retry-after"), attempt)
                        continue
                    response.raise_for_status()
                    with temporary.open("wb") as output:
                        for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                            if not chunk:
                                continue
                            output.write(chunk)
                            digest.update(chunk)
                            size += len(chunk)
                    content_length = response.headers.get("content-length")
                    if (
                        content_length
                        and not response.headers.get("content-encoding")
                        and size != int(content_length)
                    ):
                        raise httpx.ReadError(
                            f"Expected {content_length} bytes but received {size}",
                            request=response.request,
                        )
                    etag = response.headers.get("etag")
                    last_modified = response.headers.get("last-modified")
                    content_type = response.headers.get("content-type")
            break
        except (httpx.TransportError, OSError):
            temporary.unlink(missing_ok=True)
            if attempt == _MAX_DOWNLOAD_ATTEMPTS:
                raise
            _wait_before_retry(None, attempt)
    else:  # pragma: no cover - loop either breaks or raises
        raise RuntimeError(f"Download attempts exhausted for {artifact.url}")
    actual_sha256 = digest.hexdigest()
    if artifact.expected_sha256 and actual_sha256 != artifact.expected_sha256:
        temporary.unlink(missing_ok=True)
        raise ReleaseValidationError(
            f"Upstream SHA-256 mismatch for {artifact.filename}: "
            f"expected {artifact.expected_sha256}, received {actual_sha256}"
        )
    if artifact.expected_bytes is not None and size != artifact.expected_bytes:
        temporary.unlink(missing_ok=True)
        raise ReleaseValidationError(
            f"Upstream byte-count mismatch for {artifact.filename}: "
            f"expected {artifact.expected_bytes}, received {size}"
        )
    os.replace(temporary, destination)

    extracted_files: list[str] = []
    if destination.suffix.lower() == ".zip":
        extract_root = run_root / "extracted" / str(artifact.role)
        extracted_files = [
            str(path.relative_to(run_root)) for path in safe_extract_zip(destination, extract_root)
        ]

    return StoredArtifact(
        role=artifact.role,
        source_url=artifact.url,
        filename=artifact.filename,
        relative_path=str(destination.relative_to(run_root)),
        sha256=actual_sha256,
        bytes=size,
        content_type=content_type,
        etag=etag,
        upstream_last_modified=last_modified,
        extracted_files=extracted_files,
        documentation=artifact.documentation,
    )


def _wait_before_retry(retry_after: str | None, attempt: int) -> None:
    try:
        delay = float(retry_after) if retry_after is not None else float(2 ** (attempt - 1))
    except ValueError:
        delay = float(2 ** (attempt - 1))
    time.sleep(min(max(delay, 0.0), 30.0))


def _merge_validation(first: ValidationResult, second: ValidationResult) -> ValidationResult:
    checks = {**first.checks, **second.checks}
    notes = [*first.notes, *second.notes]
    return ValidationResult(passed=all(checks.values()), checks=checks, notes=notes)


def _normalized_asset(run_root: Path, path: Path) -> NormalizedAsset:
    resolved = path.resolve()
    root = run_root.resolve()
    if resolved == root or root not in resolved.parents or not resolved.is_file():
        raise ValueError(f"Normalizer produced an invalid path: {path}")
    relative = resolved.relative_to(root)
    digest = hashlib.sha256()
    with resolved.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    rows = columns = None
    if resolved.suffix.lower() == ".parquet":
        metadata = pq.read_metadata(resolved)
        rows = metadata.num_rows
        columns = metadata.num_columns
    return NormalizedAsset(
        name=resolved.stem,
        relative_path=str(relative),
        format=resolved.suffix.lower().lstrip("."),
        sha256=digest.hexdigest(),
        bytes=resolved.stat().st_size,
        rows=rows,
        columns=columns,
    )


def _write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _remove_incoming_run(path: Path, incoming_root: Path) -> None:
    resolved = path.resolve()
    expected_root = incoming_root.resolve()
    if resolved == expected_root or expected_root not in resolved.parents:
        raise ValueError(f"Refusing to remove non-incoming path: {resolved}")
    shutil.rmtree(resolved)
