from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin, urlparse

import httpx
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
from pydantic import AnyHttpUrl, TypeAdapter
from selectolax.parser import HTMLParser

from microdata_lab.adapters.base import SourceAdapter
from microdata_lab.models import (
    ArtifactRole,
    DiscoveredArtifact,
    DiscoveredRelease,
    StoredArtifact,
    ValidationResult,
)
from microdata_lab.scf_validation import validate_scf_files

SCF_LANDING_PAGE = "https://www.federalreserve.gov/econres/scfindex.htm"
_HTTP_URL = TypeAdapter(AnyHttpUrl)

_ROLE_PATTERNS: tuple[tuple[ArtifactRole, re.Pattern[str]], ...] = (
    (ArtifactRole.REPLICATE_WEIGHTS_STATA, re.compile(r"/scf(?P<year>\d{4})rw1s\.zip$", re.I)),
    (ArtifactRole.FULL_DATA_STATA, re.compile(r"/scf(?P<year>\d{4})s\.zip$", re.I)),
    (ArtifactRole.SUMMARY_EXTRACT_CSV, re.compile(r"/scfp(?P<year>\d{4})excel\.zip$", re.I)),
    (ArtifactRole.SUMMARY_EXTRACT_STATA, re.compile(r"/scfp(?P<year>\d{4})s\.zip$", re.I)),
    (ArtifactRole.CODEBOOK, re.compile(r"/codebk(?P<year>\d{4})\.txt$", re.I)),
    (ArtifactRole.CHANGES, re.compile(r"/(?P<year>\d{4})_scf_changes\.txt$", re.I)),
)

_GLOBAL_PATTERNS: tuple[tuple[ArtifactRole, re.Pattern[str]], ...] = (
    (
        ArtifactRole.STANDARD_ERROR_DOCUMENTATION,
        re.compile(r"/Standard_Error_Documentation\.pdf$", re.I),
    ),
    (ArtifactRole.VARIABLE_DEFINITIONS, re.compile(r"/bulletin\.macro\.txt$", re.I)),
)


class SCFAdapter(SourceAdapter):
    slug = "scf"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._owns_client = client is None
        self._release_index: (
            tuple[
                dict[int, dict[ArtifactRole, DiscoveredArtifact]],
                dict[ArtifactRole, DiscoveredArtifact],
            ]
            | None
        ) = None
        self.client = client or httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(60.0),
            transport=httpx.HTTPTransport(retries=3),
            headers={"User-Agent": "microdata-lab/0.1"},
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> SCFAdapter:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def discover(self, year: int | None = None) -> DiscoveredRelease:
        by_year, global_artifacts = self._load_release_index()
        available = self.available_years()
        if not available:
            raise ValueError("The official SCF page contained no complete public-data releases")
        selected_year = year if year is not None else available[-1]
        if selected_year not in available:
            raise ValueError(
                f"SCF {selected_year} was not found as a complete official release; "
                f"available years: {available}"
            )

        selected = dict(by_year[selected_year])
        selected.update(global_artifacts)
        return DiscoveredRelease(
            survey=self.slug,
            year=selected_year,
            landing_page=_HTTP_URL.validate_python(SCF_LANDING_PAGE),
            artifacts=[selected[role] for role in ArtifactRole],
        )

    def available_years(self) -> list[int]:
        by_year, global_artifacts = self._load_release_index()
        return sorted(
            year
            for year, artifacts in by_year.items()
            if not (set(ArtifactRole) - (set(artifacts) | set(global_artifacts)))
        )

    def validate_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> ValidationResult:
        extracted_files: dict[ArtifactRole, Path] = {}
        checks: dict[str, bool] = {}
        for role, suffix in {
            ArtifactRole.SUMMARY_EXTRACT_CSV: ".csv",
            ArtifactRole.REPLICATE_WEIGHTS_STATA: ".dta",
            ArtifactRole.FULL_DATA_STATA: ".dta",
            ArtifactRole.SUMMARY_EXTRACT_STATA: ".dta",
        }.items():
            matches = [
                run_root / relative_path
                for artifact in artifacts
                if artifact.role == role
                for relative_path in artifact.extracted_files
                if relative_path.lower().endswith(suffix)
            ]
            checks[f"{role.value}_contains_{suffix[1:]}"] = len(matches) == 1
            if matches:
                extracted_files[role] = matches[0]

        if not all(checks.values()):
            failed = [name for name, passed in checks.items() if not passed]
            return ValidationResult(
                passed=False,
                checks=checks,
                notes=[f"SCF extracted-file validation failed: {', '.join(failed)}"],
            )

        design_checks, notes = validate_scf_files(
            extracted_files[ArtifactRole.SUMMARY_EXTRACT_CSV],
            extracted_files[ArtifactRole.REPLICATE_WEIGHTS_STATA],
            extracted_files[ArtifactRole.FULL_DATA_STATA],
            year=release.year,
        )
        checks.update(design_checks)
        return ValidationResult(passed=all(checks.values()), checks=checks, notes=notes)

    def normalize_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> list[Path]:
        summary_files = [
            run_root / relative_path
            for artifact in artifacts
            if artifact.role == ArtifactRole.SUMMARY_EXTRACT_CSV
            for relative_path in artifact.extracted_files
            if relative_path.lower().endswith(".csv")
        ]
        if len(summary_files) != 1:
            raise ValueError(f"SCF {release.year} normalization requires one summary CSV")
        output = run_root / "normalized" / "summary_extract.parquet"
        output.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pacsv.read_csv(summary_files[0]), output, compression="zstd")
        return [output]

    def _load_release_index(
        self,
    ) -> tuple[
        dict[int, dict[ArtifactRole, DiscoveredArtifact]],
        dict[ArtifactRole, DiscoveredArtifact],
    ]:
        if self._release_index is not None:
            return self._release_index
        response = self.client.get(SCF_LANDING_PAGE)
        response.raise_for_status()
        links = list(_links(response.text))

        by_year: dict[int, dict[ArtifactRole, DiscoveredArtifact]] = {}
        global_artifacts: dict[ArtifactRole, DiscoveredArtifact] = {}
        for href, link_text in links:
            absolute = urljoin(SCF_LANDING_PAGE, href)
            path = urlparse(absolute).path
            matched = False
            for role, pattern in _ROLE_PATTERNS:
                match = pattern.search(path)
                if match:
                    release_year = int(match.group("year"))
                    by_year.setdefault(release_year, {}).setdefault(
                        role, _artifact(role, absolute, link_text)
                    )
                    matched = True
                    break
            if matched:
                continue
            for role, pattern in _GLOBAL_PATTERNS:
                if pattern.search(path):
                    global_artifacts.setdefault(role, _artifact(role, absolute, link_text))
                    break

        if not by_year:
            raise ValueError("The official SCF page contained no recognized public-data releases")
        self._release_index = by_year, global_artifacts
        return self._release_index


def _links(html: str) -> Iterable[tuple[str, str]]:
    tree = HTMLParser(html)
    for anchor in tree.css("a[href]"):
        href = (anchor.attributes.get("href") or "").strip()
        if href:
            yield href, " ".join(anchor.text(strip=True).split())


def _artifact(role: ArtifactRole, url: str, link_text: str) -> DiscoveredArtifact:
    filename = PurePosixPath(urlparse(url).path).name
    return DiscoveredArtifact(
        role=role,
        url=_HTTP_URL.validate_python(url),
        link_text=link_text,
        filename=filename,
        documentation=role
        in {
            ArtifactRole.CODEBOOK,
            ArtifactRole.STANDARD_ERROR_DOCUMENTATION,
            ArtifactRole.CHANGES,
            ArtifactRole.VARIABLE_DEFINITIONS,
        },
    )
