from __future__ import annotations

import math
import re
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urljoin, urlparse

import httpx
import pandas as pd
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
import pyreadstat
import yaml
from pydantic import AnyHttpUrl, BaseModel, Field, TypeAdapter
from selectolax.parser import HTMLParser

from microdata_lab.adapters.base import SourceAdapter
from microdata_lab.models import (
    ArtifactRole,
    DiscoveredArtifact,
    DiscoveredRelease,
    StoredArtifact,
    ValidationResult,
)

SHED_LANDING_PAGE = "https://www.federalreserve.gov/consumerscommunities/shed_data.htm"
_HTTP_URL = TypeAdapter(AnyHttpUrl)
_CONFIG_ROOT = Path(__file__).resolve().parents[3] / "config" / "shed"

DATA_CSV_ZIP = "data_csv_zip"
DATA_STATA_ZIP = "data_stata_zip"
CODEBOOK = ArtifactRole.CODEBOOK.value
REPORT = "report"

_DATA_PATTERN = re.compile(
    r"/SHED_public_use_data_(?P<year>\d{4})_\((?P<format>CSV|STATA)\)\.zip$",
    re.IGNORECASE,
)
_CODEBOOK_PATTERN = re.compile(
    r"/SHED[-_](?P<year>\d{4})(?:[-_])?codebook\.pdf$",
    re.IGNORECASE,
)


class SHEDBenchmarkDefinition(BaseModel):
    kind: str
    variable: str
    values: list[str | int | float]
    weight: str
    expected: float
    absolute_tolerance: float
    source_url: AnyHttpUrl


class SHEDSourceDefinition(BaseModel):
    year: int
    landing_page: AnyHttpUrl
    required_roles: list[str]
    expected_rows: int
    required_columns: list[str]
    forbidden_columns: list[str] = Field(default_factory=list)
    benchmark: SHEDBenchmarkDefinition
    report_url: AnyHttpUrl
    record_unit: str
    universe: str


class SHEDAdapter(SourceAdapter):
    slug = "shed"

    def __init__(
        self,
        client: httpx.Client | None = None,
        definition: SHEDSourceDefinition | None = None,
    ) -> None:
        self.definition = definition or _load_definition(2025)
        self._owns_client = client is None
        self.client = client or httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(60.0),
            transport=httpx.HTTPTransport(retries=3),
            headers={"User-Agent": "microdata-lab/0.1"},
        )
        self._release_index: dict[int, dict[str, DiscoveredArtifact]] | None = None

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def discover(self, year: int | None = None) -> DiscoveredRelease:
        selected_year = year if year is not None else self.definition.year
        if selected_year != self.definition.year:
            raise ValueError(
                f"SHED {selected_year} has no pinned validation definition; "
                f"configured year: {self.definition.year}"
            )
        by_year = self._load_release_index()
        artifacts = by_year.get(selected_year, {})
        required_page_roles = {DATA_CSV_ZIP, DATA_STATA_ZIP, CODEBOOK}
        missing = sorted(required_page_roles - set(artifacts))
        if missing:
            raise ValueError(
                f"SHED {selected_year} official release is incomplete; missing roles: {missing}"
            )
        selected = dict(artifacts)
        selected[REPORT] = _artifact(
            REPORT,
            str(self.definition.report_url),
            f"Economic Well-Being of U.S. Households in {selected_year}",
        )
        missing_configured = sorted(set(self.definition.required_roles) - set(selected))
        if missing_configured:
            raise ValueError(
                f"SHED {selected_year} validation definition is incomplete; "
                f"missing roles: {missing_configured}"
            )
        return DiscoveredRelease(
            survey=self.slug,
            year=selected_year,
            landing_page=self.definition.landing_page,
            artifacts=[selected[role] for role in self.definition.required_roles],
            source_metadata={
                "record_unit": self.definition.record_unit,
                "universe": self.definition.universe,
                "cross_section_weight": self.definition.benchmark.weight,
                "population_weight": "weight_pop",
                "panel_weights": ["panel_weight", "panel_weight_pop"],
                "expected_rows": self.definition.expected_rows,
                "benchmark": self.definition.benchmark.model_dump(mode="json"),
                "revision_policy": "same-URL changes create new immutable revisions",
            },
        )

    def available_years(self) -> list[int]:
        by_year = self._load_release_index()
        roles = set(by_year.get(self.definition.year, {}))
        required = {DATA_CSV_ZIP, DATA_STATA_ZIP, CODEBOOK}
        return [self.definition.year] if required <= roles else []

    def validate_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> ValidationResult:
        csv_files = _extracted_files(run_root, artifacts, DATA_CSV_ZIP, ".csv")
        stata_files = _extracted_files(run_root, artifacts, DATA_STATA_ZIP, ".dta")
        checks: dict[str, bool] = {
            "shed_csv_archive_contains_one_csv": len(csv_files) == 1,
            "shed_stata_archive_contains_one_dta": len(stata_files) == 1,
        }
        notes: list[str] = []
        if not all(checks.values()):
            failed = [name for name, passed in checks.items() if not passed]
            return ValidationResult(
                passed=False,
                checks=checks,
                notes=[f"SHED extracted-file validation failed: {', '.join(failed)}"],
            )

        csv_path = csv_files[0]
        header = list(pd.read_csv(csv_path, nrows=0).columns)
        columns = set(header)
        required_columns = set(self.definition.required_columns)
        checks["shed_required_columns_present"] = required_columns <= columns
        checks["shed_removed_columns_absent"] = not (
            set(self.definition.forbidden_columns) & columns
        )

        _, stata_meta = pyreadstat.read_dta(stata_files[0], metadataonly=True)
        stata_columns = set(stata_meta.column_names)
        checks["shed_stata_required_columns_present"] = required_columns <= stata_columns
        checks["shed_csv_stata_row_counts_match"] = (
            stata_meta.number_rows == self.definition.expected_rows
        )

        read_columns = sorted(
            required_columns
            | {
                self.definition.benchmark.variable,
                self.definition.benchmark.weight,
            }
        )
        row_count = 0
        respondent_ids: set[str] = set()
        duplicate_ids = False
        years: set[int] = set()
        weights_valid = True
        population_weights_valid = True
        weighted_population = 0.0
        benchmark_weight = 0.0
        benchmark_numerator = 0.0

        for chunk in pd.read_csv(csv_path, usecols=read_columns, chunksize=10_000):
            row_count += len(chunk)
            ids = chunk["shedid"].astype(str)
            if ids.duplicated().any() or respondent_ids.intersection(ids):
                duplicate_ids = True
            respondent_ids.update(ids)
            years.update(int(value) for value in chunk["year"].dropna().unique())

            weights = pd.to_numeric(chunk[self.definition.benchmark.weight], errors="coerce")
            pop_weights = pd.to_numeric(chunk["weight_pop"], errors="coerce")
            weights_valid &= bool(weights.notna().all() and (weights > 0).all())
            population_weights_valid &= bool(pop_weights.notna().all() and (pop_weights > 0).all())
            weighted_population += float(pop_weights.dropna().sum())

            values = chunk[self.definition.benchmark.variable]
            valid = values.notna() & weights.notna()
            selected = valid & values.isin(self.definition.benchmark.values)
            benchmark_weight += float(weights[valid].sum())
            benchmark_numerator += float(weights[selected].sum())

        observed = benchmark_numerator / benchmark_weight if benchmark_weight > 0 else math.nan
        checks.update(
            {
                "shed_row_count_matches_codebook": row_count == self.definition.expected_rows,
                "shed_respondent_ids_unique": not duplicate_ids
                and len(respondent_ids) == row_count,
                "shed_year_matches_release": years == {release.year},
                "shed_cross_section_weights_positive": weights_valid,
                "shed_population_weights_positive": population_weights_valid,
                "shed_official_benchmark": math.isfinite(observed)
                and abs(observed - self.definition.benchmark.expected)
                <= self.definition.benchmark.absolute_tolerance,
            }
        )
        notes.extend(
            [
                f"rows={row_count}",
                f"columns={len(header)}",
                f"weighted_population={weighted_population:.6f}",
                f"benchmark_observed={observed:.8f}",
                f"benchmark_expected={self.definition.benchmark.expected:.8f}",
                f"benchmark_source={self.definition.benchmark.source_url}",
                "weight=weight (single-year cross-section; official published-statistics weight)",
                "uncertainty=public release provides analysis weights but no replicate weights",
                "imputation=variable-level *_iflag fields distinguish imputed values "
                "where supplied",
            ]
        )
        return ValidationResult(passed=all(checks.values()), checks=checks, notes=notes)

    def normalize_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> list[Path]:
        csv_files = _extracted_files(run_root, artifacts, DATA_CSV_ZIP, ".csv")
        if len(csv_files) != 1:
            raise ValueError(f"SHED {release.year} normalization requires one CSV file")
        output = run_root / "normalized" / "respondents.parquet"
        output.parent.mkdir(parents=True, exist_ok=True)
        table = pacsv.read_csv(csv_files[0])
        pq.write_table(table, output, compression="zstd")
        return [output]

    def _load_release_index(self) -> dict[int, dict[str, DiscoveredArtifact]]:
        if self._release_index is not None:
            return self._release_index
        response = self.client.get(str(self.definition.landing_page))
        response.raise_for_status()
        by_year: dict[int, dict[str, DiscoveredArtifact]] = {}
        for href, link_text in _links(response.text):
            absolute = urljoin(str(self.definition.landing_page), href)
            path = unquote(urlparse(absolute).path)
            data_match = _DATA_PATTERN.search(path)
            if data_match:
                year = int(data_match.group("year"))
                role = (
                    DATA_CSV_ZIP if data_match.group("format").upper() == "CSV" else DATA_STATA_ZIP
                )
                by_year.setdefault(year, {}).setdefault(role, _artifact(role, absolute, link_text))
                continue
            codebook_match = _CODEBOOK_PATTERN.search(path)
            if codebook_match:
                year = int(codebook_match.group("year"))
                by_year.setdefault(year, {}).setdefault(
                    CODEBOOK, _artifact(CODEBOOK, absolute, link_text)
                )
        if not by_year:
            raise ValueError("The official SHED data page contained no recognized releases")
        self._release_index = by_year
        return by_year


def _load_definition(year: int) -> SHEDSourceDefinition:
    path = _CONFIG_ROOT / f"{year}.yaml"
    if not path.is_file():
        raise ValueError(f"SHED {year} has no pinned source definition at {path}")
    return SHEDSourceDefinition.model_validate(yaml.safe_load(path.read_text()))


def _links(html: str) -> Iterable[tuple[str, str]]:
    tree = HTMLParser(html)
    for anchor in tree.css("a[href]"):
        href = (anchor.attributes.get("href") or "").strip()
        if href:
            yield href, " ".join(anchor.text(strip=True).split())


def _artifact(role: str, url: str, link_text: str) -> DiscoveredArtifact:
    filename = PurePosixPath(unquote(urlparse(url).path)).name
    return DiscoveredArtifact(
        role=role,
        url=_HTTP_URL.validate_python(url),
        link_text=link_text,
        filename=filename,
        documentation=role in {CODEBOOK, REPORT},
    )


def _extracted_files(
    run_root: Path,
    artifacts: list[StoredArtifact],
    role: str,
    suffix: str,
) -> list[Path]:
    return [
        run_root / relative_path
        for artifact in artifacts
        if (artifact.role.value if isinstance(artifact.role, ArtifactRole) else artifact.role)
        == role
        for relative_path in artifact.extracted_files
        if relative_path.lower().endswith(suffix)
    ]
