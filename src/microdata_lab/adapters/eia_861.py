"""Official EIA Form 861 annual utility-data adapter."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

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
REFERENCE_YEAR = 2024
LANDING_PAGE = "https://www.eia.gov/electricity/data/eia861/"
ARCHIVE_URL = "https://www.eia.gov/electricity/data/eia861/zip/f8612024.zip"
ARCHIVE_ROLE = "form_861_zip"
WORKBOOK_NAME = "Sales_Ult_Cust_2024.xlsx"
DATA_TYPE_COLUMN = "Data Type\nO = Observed\nI = Imputed"
REQUIRED_COLUMNS = {
    "Data Year",
    "Utility Number",
    "Utility Name",
    "Service Type",
    DATA_TYPE_COLUMN,
    "State",
    "Ownership",
    "BA Code",
    "Thousand Dollars",
    "Megawatthours",
    "Count",
}
OWNERSHIP_CLASSES = {"Municipal", "Investor Owned", "Cooperative", "Federal"}


def _artifact_path(artifacts: list[StoredArtifact], run_root: Path) -> Path:
    for artifact in artifacts:
        if str(artifact.role) == ARCHIVE_ROLE:
            return run_root / artifact.relative_path
    raise ValueError(f"Missing required artifact role: {ARCHIVE_ROLE}")


def _read_sales_workbook(archive_path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(archive_path) as bundle:
        members = [name for name in bundle.namelist() if Path(name).name == WORKBOOK_NAME]
        if len(members) != 1:
            raise ValueError(f"Expected exactly one {WORKBOOK_NAME} in {archive_path.name}")
        workbook = io.BytesIO(bundle.read(members[0]))
    return pd.read_excel(workbook, sheet_name="States", header=2)


class EIA861Adapter(SourceAdapter):
    """Acquire and normalize EIA Form 861 utility-level sales data."""

    slug = "eia_861"

    def available_years(self) -> list[int]:
        return [REFERENCE_YEAR]

    def discover(self, year: int | None = None) -> DiscoveredRelease:
        selected_year = year or REFERENCE_YEAR
        if selected_year != REFERENCE_YEAR:
            raise ValueError(f"eia_861 only supports {REFERENCE_YEAR}")
        return DiscoveredRelease(
            survey=self.slug,
            year=selected_year,
            landing_page=_url.validate_python(LANDING_PAGE),
            artifacts=[
                DiscoveredArtifact(
                    role=ARCHIVE_ROLE,
                    url=_url.validate_python(ARCHIVE_URL),
                    filename=f"f861{selected_year}.zip",
                    link_text=f"EIA Form 861 final data files, {selected_year}",
                )
            ],
            source_metadata={
                "record_unit": "utility_service_type",
                "form": "EIA-861",
                "table": "Sales to Ultimate Customers",
                "terms": "EIA data may be reused with acknowledgment",
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
        archive_path = _artifact_path(artifacts, run_root)
        checks["archive_present"] = archive_path.is_file()
        if not checks["archive_present"]:
            return ValidationResult(passed=False, checks=checks, notes=notes)

        try:
            frame = _read_sales_workbook(archive_path)
        except (KeyError, OSError, ValueError, zipfile.BadZipFile) as error:
            checks["sales_workbook_readable"] = False
            notes.append(str(error))
            return ValidationResult(passed=False, checks=checks, notes=notes)

        checks["sales_workbook_readable"] = True
        checks["required_columns_present"] = REQUIRED_COLUMNS.issubset(frame.columns)
        if not checks["required_columns_present"]:
            missing = sorted(REQUIRED_COLUMNS.difference(frame.columns))
            notes.append(f"missing_columns={','.join(missing)}")
            return ValidationResult(passed=False, checks=checks, notes=notes)

        years = pd.to_numeric(frame["Data Year"], errors="coerce").dropna()
        observed = frame[frame[DATA_TYPE_COLUMN] == "O"]
        revenue = pd.to_numeric(observed["Thousand Dollars"], errors="coerce")
        sales = pd.to_numeric(observed["Megawatthours"], errors="coerce")
        valid = revenue.notna() & sales.notna() & (sales > 0)
        national_average = float(revenue[valid].sum() * 100 / sales[valid].sum())

        checks["reference_year_matches"] = bool(
            not years.empty and set(years.astype(int).unique()) == {release.year}
        )
        checks["observed_rows_present"] = len(observed) >= 4
        checks["ownership_classes_present"] = OWNERSHIP_CLASSES.issubset(
            set(observed["Ownership"].dropna().astype(str))
        )
        checks["residential_values_present"] = bool(valid.any())
        checks["national_price_plausible"] = 10.0 <= national_average <= 20.0
        notes.extend(
            [
                f"rows={len(frame)}",
                f"observed_rows={len(observed)}",
                f"national_residential_price_cents_per_kwh={national_average:.6f}",
            ]
        )
        return ValidationResult(passed=all(checks.values()), checks=checks, notes=notes)

    def normalize_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> list[Path]:
        del release
        frame = _read_sales_workbook(_artifact_path(artifacts, run_root))
        normalized = frame[
            [
                "Data Year",
                "Utility Number",
                "Utility Name",
                "Service Type",
                DATA_TYPE_COLUMN,
                "State",
                "Ownership",
                "BA Code",
                "Thousand Dollars",
                "Megawatthours",
                "Count",
            ]
        ].rename(
            columns={
                "Data Year": "data_year",
                "Utility Number": "utility_number",
                "Utility Name": "utility_name",
                "Service Type": "service_type",
                DATA_TYPE_COLUMN: "data_type",
                "State": "state",
                "Ownership": "ownership",
                "BA Code": "ba_code",
                "Thousand Dollars": "res_revenue_thousand_dollars",
                "Megawatthours": "res_sales_mwh",
                "Count": "res_customers",
            }
        )
        for column in (
            "data_year",
            "utility_number",
            "res_revenue_thousand_dollars",
            "res_sales_mwh",
            "res_customers",
        ):
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

        out_dir = run_root / "normalized"
        out_dir.mkdir(exist_ok=True)
        output = out_dir / "eia_861_sales.parquet"
        normalized.to_parquet(output, index=False)
        return [output]
