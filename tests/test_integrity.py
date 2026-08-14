from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import AnyHttpUrl, TypeAdapter

from microdata_lab.integrity import release_digest, scrub_data_lake
from microdata_lab.models import (
    DiscoveredRelease,
    NormalizedAsset,
    ReleaseManifest,
    StoredArtifact,
    ValidationResult,
)

_HTTP_URL = TypeAdapter(AnyHttpUrl)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _fixture_lake(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "lake"
    artifact_content = b"official artifact\n"
    normalized_content = b"normalized asset\n"
    artifact = StoredArtifact(
        role="data",
        source_url=_HTTP_URL.validate_python("https://official.test/data.csv"),
        filename="data.csv",
        relative_path="artifacts/data/data.csv",
        sha256=_sha256(artifact_content),
        bytes=len(artifact_content),
    )
    normalized = NormalizedAsset(
        name="demo-2024",
        relative_path="normalized/demo-2024.parquet",
        format="parquet",
        sha256=_sha256(normalized_content),
        bytes=len(normalized_content),
        rows=1,
        columns=1,
    )
    digest = release_digest([artifact])
    release_root = root / "releases" / "demo" / "2024" / digest
    artifact_path = release_root / artifact.relative_path
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_bytes(artifact_content)
    normalized_path = release_root / normalized.relative_path
    normalized_path.parent.mkdir(parents=True)
    normalized_path.write_bytes(normalized_content)
    discovered = DiscoveredRelease(
        survey="demo",
        year=2024,
        landing_page=_HTTP_URL.validate_python("https://official.test/releases"),
        artifacts=[],
    )
    manifest = ReleaseManifest(
        survey="demo",
        year=2024,
        release_id=f"demo-2024-{digest[:12]}",
        landing_page=discovered.landing_page,
        discovered_at=discovered.discovered_at,
        release_sha256=digest,
        artifacts=[artifact],
        normalized_assets=[normalized],
        validation=ValidationResult(passed=True, checks={"fixture": True}),
    )
    (release_root / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n")
    current_root = root / "current"
    current_root.mkdir(parents=True)
    (current_root / "demo.json").write_text(
        json.dumps(
            {
                "survey": "demo",
                "year": 2024,
                "release_id": manifest.release_id,
                "release_sha256": digest,
                "release_path": str(release_root),
            }
        )
        + "\n"
    )
    return root, artifact_path


def test_scrub_data_lake_verifies_all_manifest_files_and_pointer(tmp_path: Path) -> None:
    root, _ = _fixture_lake(tmp_path)

    summary = scrub_data_lake(root)

    assert summary.passed is True
    assert summary.releases_checked == 1
    assert summary.pointers_checked == 1
    assert summary.files_checked == 2
    assert summary.bytes_checked == len(b"official artifact\nnormalized asset\n")


def test_scrub_data_lake_reports_tampering_without_modifying_file(tmp_path: Path) -> None:
    root, artifact_path = _fixture_lake(tmp_path)
    artifact_path.write_bytes(b"tampered")

    summary = scrub_data_lake(root)

    assert summary.passed is False
    assert any("byte count mismatch" in error for error in summary.errors)
    assert any("SHA-256 mismatch" in error for error in summary.errors)
    assert artifact_path.read_bytes() == b"tampered"
