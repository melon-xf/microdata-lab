from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from microdata_lab.models import RELEASE_SCHEMA_VERSION, ReleaseManifest, StoredArtifact


@dataclass(frozen=True)
class IntegritySummary:
    releases_checked: int
    pointers_checked: int
    files_checked: int
    bytes_checked: int
    errors: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.errors


def release_digest(
    artifacts: Iterable[StoredArtifact], *, schema_version: int = RELEASE_SCHEMA_VERSION
) -> str:
    digest = hashlib.sha256()
    if schema_version >= 2:
        digest.update(f"release-schema:{schema_version}\n".encode())
    for artifact in sorted(artifacts, key=lambda item: str(item.role)):
        digest.update(f"{artifact.role}:{artifact.sha256}\n".encode())
    return digest.hexdigest()


def scrub_data_lake(data_root: Path) -> IntegritySummary:
    root = data_root.expanduser().resolve()
    releases_root = (root / "releases").resolve()
    errors: list[str] = []
    releases_checked = pointers_checked = files_checked = bytes_checked = 0
    manifests: dict[Path, ReleaseManifest] = {}

    for manifest_path in sorted(releases_root.glob("*/*/*/manifest.json")):
        release_root = manifest_path.parent.resolve()
        try:
            manifest = ReleaseManifest.model_validate_json(manifest_path.read_text())
        except (OSError, ValidationError, ValueError) as error:
            errors.append(f"invalid manifest {manifest_path}: {error}")
            continue
        manifests[release_root] = manifest
        releases_checked += 1

        expected_digest = release_digest(manifest.artifacts, schema_version=manifest.schema_version)
        if manifest.release_sha256 != expected_digest:
            errors.append(f"release digest mismatch: {release_root}")
        if release_root.name != manifest.release_sha256:
            errors.append(f"release directory mismatch: {release_root}")
        if manifest.schema_version >= 2:
            expected_id = f"{manifest.survey}-{manifest.year}-{manifest.release_sha256[:12]}"
            if manifest.release_id != expected_id:
                errors.append(f"release ID mismatch: {release_root}")
        if not manifest.validation.passed:
            errors.append(f"release manifest is not validated: {release_root}")

        for relative_path, expected_bytes, expected_sha256 in [
            *[
                (artifact.relative_path, artifact.bytes, artifact.sha256)
                for artifact in manifest.artifacts
            ],
            *[
                (asset.relative_path, asset.bytes, asset.sha256)
                for asset in manifest.normalized_assets
            ],
        ]:
            candidate = _contained_file(release_root, relative_path)
            if candidate is None:
                errors.append(f"unsafe or missing release file: {release_root}/{relative_path}")
                continue
            actual_bytes = candidate.stat().st_size
            files_checked += 1
            bytes_checked += actual_bytes
            if actual_bytes != expected_bytes:
                errors.append(f"byte count mismatch: {candidate}")
            if _sha256_file(candidate) != expected_sha256:
                errors.append(f"SHA-256 mismatch: {candidate}")

    current_root = root / "current"
    for pointer_path in sorted(current_root.glob("*.json")):
        pointers_checked += 1
        try:
            pointer = json.loads(pointer_path.read_text())
            release_path = Path(pointer["release_path"]).expanduser().resolve()
        except (KeyError, OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"invalid current pointer {pointer_path}: {error}")
            continue
        if release_path == releases_root or releases_root not in release_path.parents:
            errors.append(f"current pointer escapes releases root: {pointer_path}")
            continue
        pointer_manifest = manifests.get(release_path)
        if pointer_manifest is None:
            errors.append(f"current pointer target is not a scrubbed release: {pointer_path}")
            continue
        expected = {
            "survey": pointer_manifest.survey,
            "year": pointer_manifest.year,
            "release_id": pointer_manifest.release_id,
            "release_sha256": pointer_manifest.release_sha256,
        }
        for field, expected_value in expected.items():
            if pointer.get(field) != expected_value:
                errors.append(f"current pointer {field} mismatch: {pointer_path}")
        if pointer_path.stem != pointer_manifest.survey:
            errors.append(f"current pointer filename mismatch: {pointer_path}")

    return IntegritySummary(
        releases_checked=releases_checked,
        pointers_checked=pointers_checked,
        files_checked=files_checked,
        bytes_checked=bytes_checked,
        errors=tuple(errors),
    )


def _contained_file(root: Path, relative_path: str) -> Path | None:
    candidate = (root / relative_path).resolve()
    if candidate == root or root not in candidate.parents or not candidate.is_file():
        return None
    return candidate


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
