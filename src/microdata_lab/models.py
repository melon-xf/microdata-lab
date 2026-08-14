from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import AnyHttpUrl, BaseModel, Field

RELEASE_SCHEMA_VERSION = 2


class ArtifactRole(StrEnum):
    FULL_DATA_STATA = "full_data_stata"
    REPLICATE_WEIGHTS_STATA = "replicate_weights_stata"
    SUMMARY_EXTRACT_CSV = "summary_extract_csv"
    SUMMARY_EXTRACT_STATA = "summary_extract_stata"
    CODEBOOK = "codebook"
    STANDARD_ERROR_DOCUMENTATION = "standard_error_documentation"
    CHANGES = "changes"
    VARIABLE_DEFINITIONS = "variable_definitions"


class DiscoveredArtifact(BaseModel):
    role: ArtifactRole | str
    url: AnyHttpUrl
    link_text: str
    filename: str
    documentation: bool = False
    expected_sha256: str | None = None
    expected_bytes: int | None = None
    request_payload: dict[str, Any] | None = None


class DiscoveredRelease(BaseModel):
    survey: str
    year: int
    landing_page: AnyHttpUrl
    artifacts: list[DiscoveredArtifact]
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def release_label(self) -> str:
        return f"{self.survey}-{self.year}"


class StoredArtifact(BaseModel):
    role: ArtifactRole | str
    source_url: AnyHttpUrl
    filename: str
    relative_path: str
    sha256: str
    bytes: int
    content_type: str | None = None
    etag: str | None = None
    upstream_last_modified: str | None = None
    extracted_files: list[str] = Field(default_factory=list)
    documentation: bool = False


class ValidationResult(BaseModel):
    passed: bool
    checks: dict[str, bool]
    notes: list[str] = Field(default_factory=list)


class NormalizedAsset(BaseModel):
    name: str
    relative_path: str
    format: str
    sha256: str
    bytes: int
    rows: int | None = None
    columns: int | None = None


class ReleaseManifest(BaseModel):
    schema_version: int = RELEASE_SCHEMA_VERSION
    survey: str
    year: int
    release_id: str
    landing_page: AnyHttpUrl
    discovered_at: datetime
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    release_sha256: str
    artifacts: list[StoredArtifact]
    normalized_assets: list[NormalizedAsset] = Field(default_factory=list)
    validation: ValidationResult
    source_metadata: dict[str, Any] = Field(default_factory=dict)
