"""Keyless official-series adapter for the Hormuz energy and inflation watch."""

from __future__ import annotations

from pathlib import Path

import httpx
import pandas as pd
from pydantic import AnyHttpUrl, TypeAdapter

from microdata_lab.adapters.base import SourceAdapter
from microdata_lab.models import (
    DiscoveredArtifact,
    DiscoveredRelease,
    StoredArtifact,
    ValidationResult,
)

_url = TypeAdapter(AnyHttpUrl)
REFERENCE_YEAR = 2026
LANDING_PAGE = "https://fred.stlouisfed.org/"
START_DATE = "2026-02-01"
HORMUZ_SHEET = "CrudeAndProducts"
HORMUZ_TOTAL_LABEL = "Total oil flows through Strait of Hormuz"
EXPECTED_HORMUZ_FLOW_2024 = 20.261741721311477
SERIES = {
    "brent_csv": {
        "id": "DCOILBRENTEU",
        "title": "Brent crude oil spot price",
        "unit": "dollars_per_barrel",
        "frequency": "daily",
    },
    "gasoline_csv": {
        "id": "GASREGW",
        "title": "U.S. regular gasoline price",
        "unit": "dollars_per_gallon",
        "frequency": "weekly",
    },
    "breakeven_csv": {
        "id": "T5YIE",
        "title": "5-year breakeven inflation rate",
        "unit": "percent",
        "frequency": "daily",
    },
}
HORMUZ_URL = "https://www.eia.gov/todayinenergy/images/2025.06.16/fig1.xlsx"


def read_hormuz_flow_2024(path: Path) -> float:
    """Read EIA's exact 2024 total-flow value from its figure workbook."""
    frame = pd.read_excel(path, sheet_name=HORMUZ_SHEET, header=None)
    values = frame.to_numpy().tolist()
    year_cells = [
        (row_index, column_index)
        for row_index, row in enumerate(values)
        for column_index, value in enumerate(row)
        if str(value).strip() in {"2024", "2024.0"}
    ]
    total_rows = [
        row_index
        for row_index, row in enumerate(values)
        if any(str(value).strip() == HORMUZ_TOTAL_LABEL for value in row)
    ]
    if len(year_cells) != 1 or len(total_rows) != 1:
        raise ValueError("EIA Hormuz workbook labels changed")
    _, year_column = year_cells[0]
    return float(values[total_rows[0]][year_column])


class EnergyWatchAdapter(SourceAdapter):
    """Acquire the small official data surface needed for the live watch."""

    slug = "energy_watch"

    def __init__(self, *, client: httpx.Client | None = None) -> None:
        self._client = client

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                follow_redirects=True,
                timeout=httpx.Timeout(connect=20.0, read=60.0, write=30.0, pool=20.0),
            )
        return self._client

    def available_years(self) -> list[int]:
        return [REFERENCE_YEAR]

    def discover(self, year: int | None = None) -> DiscoveredRelease:
        selected_year = year or REFERENCE_YEAR
        if selected_year != REFERENCE_YEAR:
            raise ValueError(f"energy_watch only supports {REFERENCE_YEAR}")
        artifacts = [
            DiscoveredArtifact(
                role=role,
                url=_url.validate_python(
                    f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={meta['id']}&cosd={START_DATE}"
                ),
                filename=f"{meta['id']}_{selected_year}.csv",
                link_text=str(meta["title"]),
            )
            for role, meta in SERIES.items()
        ]
        artifacts.append(
            DiscoveredArtifact(
                role="hormuz_xlsx",
                url=_url.validate_python(HORMUZ_URL),
                filename="eia_hormuz_flows_2020_2025q1.xlsx",
                link_text="EIA Hormuz petroleum-flow figure data",
            )
        )
        return DiscoveredRelease(
            survey=self.slug,
            year=selected_year,
            landing_page=_url.validate_python(LANDING_PAGE),
            artifacts=artifacts,
            source_metadata={
                "record_unit": "market_observation",
                "event_baseline": "2026-02-27",
                "terms": "FRED series terms; EIA public-domain citation requested",
                "series": [meta["id"] for meta in SERIES.values()],
                "hormuz_exposure_mbd_2024": EXPECTED_HORMUZ_FLOW_2024,
                "estimated_spare_bypass_mbd": 2.6,
            },
        )

    def validate_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> ValidationResult:
        by_role = {str(artifact.role): run_root / artifact.relative_path for artifact in artifacts}
        checks: dict[str, bool] = {}
        notes: list[str] = []
        for role, meta in SERIES.items():
            path = by_role.get(role)
            present = path is not None and path.is_file()
            checks[f"{role}_present"] = present
            if not present or path is None:
                continue
            frame = pd.read_csv(path)
            series_id = str(meta["id"])
            date_column = str(frame.columns[0]) if len(frame.columns) else ""
            checks[f"{role}_schema"] = list(frame.columns[1:]) == [series_id] and date_column in {
                "DATE",
                "observation_date",
            }
            if not checks[f"{role}_schema"]:
                continue
            values = pd.to_numeric(frame[series_id], errors="coerce")
            dates = pd.to_datetime(frame[date_column], errors="coerce")
            checks[f"{role}_observations"] = bool(values.notna().sum() >= 10)
            checks[f"{role}_dates"] = bool(dates.notna().all())
            notes.append(f"{series_id}_latest={dates[values.notna()].max().date()}")
        xlsx = by_role.get("hormuz_xlsx")
        checks["hormuz_xlsx_present"] = xlsx is not None and xlsx.is_file()
        if xlsx is not None and xlsx.is_file():
            workbook = pd.ExcelFile(xlsx)
            checks["hormuz_workbook_readable"] = bool(workbook.sheet_names)
            checks["hormuz_sheet_present"] = HORMUZ_SHEET in workbook.sheet_names
            if checks["hormuz_sheet_present"]:
                flow = read_hormuz_flow_2024(xlsx)
                checks["hormuz_flow_plausible"] = 20.0 <= flow <= 20.5
                checks["hormuz_flow_benchmark"] = abs(flow - EXPECTED_HORMUZ_FLOW_2024) < 1e-9
                notes.append(f"hormuz_flow_2024_mbd={flow}")
            notes.append(f"hormuz_sheets={','.join(map(str, workbook.sheet_names))}")
        return ValidationResult(passed=all(checks.values()), checks=checks, notes=notes)

    def normalize_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> list[Path]:
        by_role = {str(artifact.role): run_root / artifact.relative_path for artifact in artifacts}
        rows: list[pd.DataFrame] = []
        for role, meta in SERIES.items():
            frame = pd.read_csv(by_role[role])
            series_id = str(meta["id"])
            date_column = str(frame.columns[0])
            normalized = frame.rename(columns={date_column: "date", series_id: "value"})
            normalized["date"] = pd.to_datetime(normalized["date"], errors="raise")
            normalized["value"] = pd.to_numeric(normalized["value"], errors="coerce")
            normalized = normalized.dropna(subset=["value"])
            normalized["series_id"] = series_id
            normalized["series_title"] = str(meta["title"])
            normalized["unit"] = str(meta["unit"])
            normalized["frequency"] = str(meta["frequency"])
            columns = ["series_id", "series_title", "date", "value", "unit", "frequency"]
            rows.append(normalized[columns])
        flow = read_hormuz_flow_2024(by_role["hormuz_xlsx"])
        rows.append(
            pd.DataFrame(
                [
                    {
                        "series_id": "EIA_HORMUZ_TOTAL_OIL",
                        "series_title": "Total oil flows through the Strait of Hormuz",
                        "date": pd.Timestamp("2024-12-31"),
                        "value": flow,
                        "unit": "million_barrels_per_day",
                        "frequency": "annual",
                    }
                ]
            )
        )
        out_dir = run_root / "normalized"
        out_dir.mkdir(exist_ok=True)
        out = out_dir / "energy_watch.parquet"
        normalized = pd.concat(rows, ignore_index=True).sort_values(["series_id", "date"])
        normalized.to_parquet(out, index=False)
        return [out]

    def download_client(self) -> httpx.Client:
        return self.client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
