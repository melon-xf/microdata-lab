"""BLS CPI-U multi-series adapter over the official time-series text files.

The complete CPI-U history is published as tab-separated text files under
https://download.bls.gov/pub/time.series/cu/ . The directory is protected by a
web application firewall: requests without an identifying User-Agent receive a
short HTML block page (HTTP 403, ~29 lines) instead of data. All downloads must
go through ``microdata_lab.bls.build_bls_client``, which sends the protected
``BLS_USER_AGENT`` identity and refuses non-BLS hosts.

Verified file layouts (fetched 2026-08):

- ``cu.series`` — one row per series: series_id, area_code, item_code,
  seasonal, periodicity_code, base_code, base_period, series_title,
  footnote_codes, begin_year, begin_period, end_year, end_period. The
  series_id column is padded with trailing spaces up to the tab separator.
- ``cu.area`` — area_code, area_name, display_level, selectable, sort_sequence.
- ``cu.item`` — item_code, item_name, display_level, selectable, sort_sequence.
- ``cu.period`` — period, period_abbr, period_name (CRLF line endings).
- ``cu.data.0.Current`` .. ``cu.data.20.USCommoditiesServicesSpecial`` — 21
  data files with columns series_id, year, period, value, footnote_codes.
  The series_id and value columns are space-padded and lines end with CRLF.

Series-id grammar (verified against cu.series): ``CU`` + seasonal code
(``U`` = not seasonally adjusted, ``S`` = seasonally adjusted) + periodicity
code (``R`` = regular/monthly) + area_code + item_code. Example:
``CUURS49ESEFV`` = CU + U + R + S49E (San Diego-Carlsbad, CA) + SEFV (Food
away from home). Parsers here always join on cu.series rather than trusting
the string layout, because area codes vary in length.

Periodicity semantics (from cu.period):

- ``M01``..``M12``: monthly index observations. Resolved to ISO month
  timestamps ``YYYY-MM-01``.
- ``M13``: annual average of the twelve monthly indexes. Not a monthly
  observation; never resolves to a month.
- ``S01``/``S02``: semiannual averages (first/second half). ``S03``: annual
  average computed from semiannual indexes; appears on some older MSA series.
  None of the S-codes resolve to a month.
- Some MSA series are published bimonthly (odd or even months only). Those
  rows still use ``M01``..``M12`` codes; gaps between published months are
  genuine non-publication, not missing data.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pandas as pd
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, TypeAdapter

from microdata_lab.adapters.base import SourceAdapter
from microdata_lab.bls import build_bls_client
from microdata_lab.models import (
    DiscoveredArtifact,
    DiscoveredRelease,
    StoredArtifact,
    ValidationResult,
)

TIME_SERIES_BASE = "https://download.bls.gov/pub/time.series/cu"
LANDING_PAGE = "https://www.bls.gov/cpi/"
_url_adapter = TypeAdapter(AnyHttpUrl)

CATALOG_SERIES = "catalog_series"
CATALOG_AREA = "catalog_area"
CATALOG_ITEM = "catalog_item"
CATALOG_PERIOD = "catalog_period"
DATA_ROLE_PREFIX = "data_"

#: Metadata files every release must contain, mapped to their artifact roles.
METADATA_FILES: dict[str, str] = {
    "cu.series": CATALOG_SERIES,
    "cu.area": CATALOG_AREA,
    "cu.item": CATALOG_ITEM,
    "cu.period": CATALOG_PERIOD,
}

#: Official observation files, enumerated from the cu/ directory listing on
#: 2026-08-12. Roles are derived as ``data_`` + sanitized filename.
DATA_FILES: tuple[str, ...] = (
    "cu.data.0.Current",
    "cu.data.1.AllItems",
    "cu.data.2.Summaries",
    "cu.data.3.AsizeNorthEast",
    "cu.data.4.AsizeNorthCentral",
    "cu.data.5.AsizeSouth",
    "cu.data.6.AsizeWest",
    "cu.data.7.OtherNorthEast",
    "cu.data.8.OtherNorthCentral",
    "cu.data.9.OtherSouth",
    "cu.data.10.OtherWest",
    "cu.data.11.USFoodBeverage",
    "cu.data.12.USHousing",
    "cu.data.13.USApparel",
    "cu.data.14.USTransportation",
    "cu.data.15.USMedical",
    "cu.data.16.USRecreation",
    "cu.data.17.USEducationAndCommunication",
    "cu.data.18.USOtherGoodsAndServices",
    "cu.data.19.PopulationSize",
    "cu.data.20.USCommoditiesServicesSpecial",
)

#: Observation files are tens of megabytes; anything tiny that is not one of
#: the small metadata files is almost certainly a WAF block page.
_MIN_DATA_BYTES = 100_000
_BLOCK_PAGE_REMEDIATION = (
    "download.bls.gov returned an HTML block page instead of data. The BLS "
    "firewall rejects generic User-Agents; configure an identifying "
    "BLS_USER_AGENT with `uv run python scripts/configure_bls_contact.py`."
)

#: Period codes that are averages rather than monthly observations.
AVERAGE_PERIODS = frozenset({"M13", "S01", "S02", "S03"})


class BlsSeriesAccessError(RuntimeError):
    """Raised when BLS serves an HTML block page instead of a text file."""


class BlsSeriesBenchmark(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_id: str = "CUURS49ASEFV"
    period: str = "1952-12"  # YYYY-MM
    expected_value: float = 20.8
    tolerance: float = 0.001
    description: str = "Food away from home, Los Angeles, first published month"


class BlsSeriesConfig(BaseModel):
    """Config schema for the CPI-U multi-series text-file adapter."""

    model_config = ConfigDict(extra="forbid")

    survey_title: str = "CPI-U time-series text files"
    landing_page: AnyHttpUrl = _url_adapter.validate_python(LANDING_PAGE)
    benchmark: BlsSeriesBenchmark = BlsSeriesBenchmark()
    terms: str = "us_federal_public_domain"
    record_unit: str = "monthly_index_observation"
    data_files: tuple[str, ...] = DATA_FILES


def looks_like_block_page(content: bytes) -> bool:
    """True when downloaded bytes are the BLS WAF denial page, not data."""
    head = content[:1024].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def data_role(filename: str) -> str:
    return DATA_ROLE_PREFIX + filename.replace(".", "_")


def decompose_series_id(series_id: str) -> dict[str, str]:
    """Split a CU series id into prefix/seasonal/periodicity/area/item.

    Prefer joining on cu.series in real work; this helper exists for logging
    and sanity checks only, because area codes vary in length.
    """
    sid = series_id.strip()
    if len(sid) < 5 or not sid.startswith("CU"):
        raise ValueError(f"Not a CPI-U series id: {series_id!r}")
    return {
        "survey_prefix": sid[:2],
        "seasonal": sid[2],
        "periodicity": sid[3],
        "area_item": sid[4:],
    }


def resolve_period_date(year: int, period: str) -> str | None:
    """Resolve a BLS period code to an ISO month timestamp.

    M01..M12 map to the first of the month. Average periods (M13 annual
    average, S01/S02 semiannual averages, S03 semiannual-based annual
    average) return None: they are not monthly observations.
    """
    period = period.strip().upper()
    if period.startswith("M") and period[1:].isdigit():
        month = int(period[1:])
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}-01"
    return None


def _parse_tsv(text: str) -> pd.DataFrame:
    """Parse a BLS tab-separated file, stripping padding and CRLF endings."""
    lines = [line for line in text.splitlines() if line.strip("\r\t ")]
    if not lines:
        return pd.DataFrame()
    columns = [cell.strip() for cell in lines[0].split("\t")]
    rows = []
    for line in lines[1:]:
        cells = [cell.strip() for cell in line.rstrip("\r\n").split("\t")]
        cells += [""] * (len(columns) - len(cells))
        rows.append(dict(zip(columns, cells[: len(columns)], strict=True)))
    return pd.DataFrame(rows, columns=columns)


def parse_catalog_series(text: str) -> pd.DataFrame:
    df = _parse_tsv(text)
    for column in ("begin_year", "end_year"):
        if column in df:
            df[column] = pd.to_numeric(df[column], errors="coerce").astype("Int64")
    return df


def parse_areas(text: str) -> pd.DataFrame:
    return _parse_tsv(text)


def parse_items(text: str) -> pd.DataFrame:
    return _parse_tsv(text)


def parse_periods(text: str) -> pd.DataFrame:
    return _parse_tsv(text)


def parse_observations(text: str, wanted: set[str] | None = None) -> pd.DataFrame:
    """Parse one cu.data.* file into series_id/year/period/value rows."""
    df = _parse_tsv(text)
    if df.empty:
        return df
    if wanted is not None:
        df = df[df["series_id"].isin(wanted)]
    df = df.copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.reset_index(drop=True)


class BlsSeriesAdapter(SourceAdapter):
    slug = "bls_series"

    def __init__(
        self,
        *,
        definition: BlsSeriesConfig | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.definition = definition or BlsSeriesConfig()
        self._client = client

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = build_bls_client()
        return self._client

    def download_client(self) -> httpx.Client:
        """Return the BLS-only client with the protected identifying User-Agent."""
        return self.client

    def available_years(self) -> list[int]:
        return [datetime.now(UTC).year]

    def discover(self, year: int | None = None) -> DiscoveredRelease:
        selected_year = year or datetime.now(UTC).year
        artifacts = [
            DiscoveredArtifact(
                role=role,
                url=_url_adapter.validate_python(f"{TIME_SERIES_BASE}/{filename}"),
                filename=filename,
                link_text=f"BLS CPI-U {filename}",
            )
            for filename, role in METADATA_FILES.items()
        ]
        artifacts += [
            DiscoveredArtifact(
                role=data_role(filename),
                url=_url_adapter.validate_python(f"{TIME_SERIES_BASE}/{filename}"),
                filename=filename,
                link_text=f"BLS CPI-U {filename}",
            )
            for filename in self.definition.data_files
        ]
        return DiscoveredRelease(
            survey=self.slug,
            year=selected_year,
            landing_page=self.definition.landing_page,
            artifacts=artifacts,
            source_metadata={
                "record_unit": self.definition.record_unit,
                "api": "BLS time-series text files (download.bls.gov)",
                "identifying_user_agent": True,
                "terms": self.definition.terms,
                "data_files": list(self.definition.data_files),
                "periodicity": (
                    "M01-M12 monthly; M13 annual average; S01/S02 semiannual "
                    "averages; S03 semiannual-based annual average"
                ),
            },
        )

    def validate_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> ValidationResult:
        checks: dict[str, bool] = {}
        notes: list[str] = []

        for artifact in artifacts:
            path = run_root / artifact.relative_path
            present = path.is_file()
            checks[f"present_{artifact.role}"] = present
            if not present:
                continue
            head = path.read_bytes()[:4096]
            is_block = looks_like_block_page(head)
            checks[f"not_block_page_{artifact.role}"] = not is_block
            if is_block:
                notes.append(f"{artifact.filename}: {_BLOCK_PAGE_REMEDIATION}")
            if (
                str(artifact.role).startswith(DATA_ROLE_PREFIX)
                and not is_block
                and artifact.bytes < _MIN_DATA_BYTES
            ):
                checks[f"plausible_size_{artifact.role}"] = False
                notes.append(
                    f"{artifact.filename} is only {artifact.bytes} bytes; a real "
                    f"cu.data.* file is orders of magnitude larger. {_BLOCK_PAGE_REMEDIATION}"
                )

        for filename, role in METADATA_FILES.items():
            if not checks.get(f"present_{role}", False):
                notes.append(f"Missing required metadata file {filename}")

        bm = self.definition.benchmark
        target_year, target_month = bm.period.split("-")
        target_period = f"M{int(target_month):02d}"
        benchmark_found = False
        for artifact in artifacts:
            role = str(artifact.role)
            if not role.startswith(DATA_ROLE_PREFIX) or not checks.get(f"not_block_page_{role}"):
                continue
            path = run_root / artifact.relative_path
            if not path.is_file():
                continue
            observed = _find_observation(path, bm.series_id, int(target_year), target_period)
            if observed is None:
                continue
            benchmark_found = True
            err = abs(observed - bm.expected_value) / bm.expected_value
            checks["benchmark_value"] = err <= bm.tolerance
            notes.append(
                f"benchmark {bm.series_id} {bm.period}={observed} "
                f"expected={bm.expected_value} ({artifact.filename})"
            )
            break
        if not benchmark_found:
            checks["benchmark_value"] = False
            notes.append(
                f"benchmark observation {bm.series_id} {bm.period} not found in any data file"
            )

        return ValidationResult(passed=all(checks.values()), checks=checks, notes=notes)

    def normalize_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> list[Path]:
        by_role = {str(a.role): run_root / a.relative_path for a in artifacts}
        out_dir = run_root / "normalized"
        out_dir.mkdir(exist_ok=True)
        written: list[Path] = []

        catalog_frames: dict[str, pd.DataFrame] = {}
        for filename, role in METADATA_FILES.items():
            path = by_role.get(role)
            if path is None or not path.is_file():
                continue
            parser = {
                CATALOG_SERIES: parse_catalog_series,
                CATALOG_AREA: parse_areas,
                CATALOG_ITEM: parse_items,
                CATALOG_PERIOD: parse_periods,
            }[role]
            catalog_frames[role] = parser(path.read_text(encoding="utf-8", errors="replace"))
            out_path = out_dir / f"{filename.replace('.', '_')}.parquet"
            catalog_frames[role].to_parquet(out_path, index=False)
            written.append(out_path)

        series = catalog_frames.get(CATALOG_SERIES)
        frames = []
        for filename in self.definition.data_files:
            path = by_role.get(data_role(filename))
            if path is None or not path.is_file():
                continue
            frames.append(
                parse_observations(path.read_text(encoding="utf-8", errors="replace"))
            )
        if frames:
            observations = pd.concat(frames, ignore_index=True)
            observations = self._attach_geography(observations, series, catalog_frames)
            out_path = out_dir / "cu_observations.parquet"
            observations.to_parquet(out_path, index=False)
            written.append(out_path)
        return written

    # ------------------------------------------------------------------
    # Public analysis API

    def fetch_catalog(self, *, client: httpx.Client | None = None) -> dict[str, pd.DataFrame]:
        """Download and parse the cu.series/cu.area/cu.item/cu.period metadata."""
        active = client or self.client
        parsers = {
            "series": ("cu.series", parse_catalog_series),
            "areas": ("cu.area", parse_areas),
            "items": ("cu.item", parse_items),
            "periods": ("cu.period", parse_periods),
        }
        return {
            name: parser(_fetch_text(active, f"{TIME_SERIES_BASE}/{filename}"))
            for name, (filename, parser) in parsers.items()
        }

    def fetch_series(
        self,
        series_ids: list[str] | None = None,
        *,
        area_codes: list[str] | None = None,
        item_codes: list[str] | None = None,
        seasonal: str | None = None,
        include_averages: bool = False,
        data_files: list[str] | None = None,
        client: httpx.Client | None = None,
    ) -> pd.DataFrame:
        """Fetch observations as a tidy DataFrame.

        Columns: series_id, date (ISO month, None for average periods),
        period, year, value, area_code, area_name. Selection is by explicit
        ``series_ids`` or by catalog filters (area_codes/item_codes/seasonal).
        ``data_files`` restricts which cu.data.* files are scanned (west-coast
        MSA series live in ``cu.data.10.OtherWest``); the default scans all.
        """
        active = client or self.client
        catalog = self.fetch_catalog(client=active)
        series = catalog["series"]

        wanted: set[str] | None = None
        if series_ids is not None:
            wanted = {sid.strip() for sid in series_ids}
        if area_codes or item_codes or seasonal:
            mask = pd.Series(True, index=series.index)
            if area_codes:
                mask &= series["area_code"].isin(area_codes)
            if item_codes:
                mask &= series["item_code"].isin(item_codes)
            if seasonal:
                mask &= series["seasonal"] == seasonal
            filtered = set(series.loc[mask, "series_id"])
            wanted = filtered if wanted is None else wanted & filtered
        if wanted is None:
            raise ValueError("Provide series_ids or at least one catalog filter")

        frames = []
        for filename in data_files or list(self.definition.data_files):
            text = _fetch_text(active, f"{TIME_SERIES_BASE}/{filename}")
            frames.append(parse_observations(text, wanted))
        observations = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if observations.empty:
            return pd.DataFrame(
                columns=["series_id", "date", "period", "year", "value", "area_code", "area_name"]
            )
        if not include_averages:
            observations = observations[~observations["period"].isin(AVERAGE_PERIODS)]
        observations = self._attach_geography(observations, series, catalog)
        observations["date"] = [
            resolve_period_date(int(year), period) if pd.notna(year) else None
            for year, period in zip(observations["year"], observations["period"], strict=True)
        ]
        observations = observations[
            ["series_id", "date", "period", "year", "value", "area_code", "area_name"]
        ].sort_values(["series_id", "year", "period"])
        return observations.reset_index(drop=True)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    @staticmethod
    def _attach_geography(
        observations: pd.DataFrame,
        series: pd.DataFrame | None,
        catalog: dict[str, pd.DataFrame],
    ) -> pd.DataFrame:
        if series is None or series.empty:
            observations = observations.copy()
            observations["area_code"] = pd.NA
            observations["area_name"] = pd.NA
            return observations
        areas = catalog.get("areas")
        if areas is None:
            areas = catalog.get(CATALOG_AREA)
        geo = series[["series_id", "area_code"]].drop_duplicates("series_id")
        if areas is not None and not areas.empty:
            geo = geo.merge(
                areas[["area_code", "area_name"]].drop_duplicates("area_code"),
                on="area_code",
                how="left",
            )
        else:
            geo["area_name"] = pd.NA
        return observations.merge(geo, on="series_id", how="left")


def _find_observation(path: Path, series_id: str, year: int, period: str) -> float | None:
    """Stream one data file for a single benchmark observation."""
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        header = handle.readline()
        if not header:
            return None
        for line in handle:
            if not line.startswith(series_id):
                continue
            cells = [cell.strip() for cell in line.rstrip("\r\n").split("\t")]
            if len(cells) < 4:
                continue
            if cells[0] == series_id and cells[1] == str(year) and cells[2] == period:
                try:
                    return float(cells[3])
                except ValueError:
                    return None
    return None


def _fetch_text(client: httpx.Client, url: str) -> str:
    """GET one text file, failing loudly on WAF block pages."""
    try:
        response = client.get(url)
    except httpx.HTTPError as error:
        raise BlsSeriesAccessError(f"Failed to reach {url}: {error}") from error
    if response.status_code != 200 or looks_like_block_page(response.content):
        raise BlsSeriesAccessError(
            f"{url} returned HTTP {response.status_code}. {_BLOCK_PAGE_REMEDIATION}"
        )
    return response.text
