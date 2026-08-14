from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from microdata_lab.models import DiscoveredRelease, StoredArtifact, ValidationResult


class SourceAdapter(ABC):
    slug: str

    @abstractmethod
    def discover(self, year: int | None = None) -> DiscoveredRelease:
        """Discover a complete official release or fail."""
        raise NotImplementedError

    def available_years(self) -> list[int]:
        """Return official release years available for deterministic backfill."""
        return [self.discover().year]

    def validate_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> ValidationResult:
        """Run source-specific raw, design, and benchmark gates."""
        return ValidationResult(passed=True, checks={}, notes=[])

    def normalize_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> list[Path]:
        """Write deterministic analysis-ready derivatives under the incoming run."""
        return []

    def download_client(self) -> httpx.Client | None:
        """Return a provider-authenticated download client when required."""
        return None

    def close(self) -> None:
        """Release network or provider resources."""
        return None

    def __enter__(self) -> SourceAdapter:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
