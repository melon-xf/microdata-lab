from __future__ import annotations

import io
import zipfile
from pathlib import Path

import httpx
import pandas as pd
import yaml
from pydantic import AnyHttpUrl, BaseModel, TypeAdapter

from microdata_lab.adapters.base import SourceAdapter
from microdata_lab.models import (
    DiscoveredArtifact,
    DiscoveredRelease,
    StoredArtifact,
    ValidationResult,
)

_url_adapter = TypeAdapter(AnyHttpUrl)

BASE_URL = "https://gss.norc.org/content/dam/gss/get-the-data/documents/stata"
CODEBOOK_URL = (
    "https://gss.norc.org/content/dam/gss/get-documentation/pdf/codebook"
    "/GSS%202024%20Codebook%20R3a.pdf"
)

DATA_STATA = "stata_zip"
CODEBOOK = "codebook_pdf"


class GSSBenchmark(BaseModel):
    variable: str
    description: str = ""
    expected_share: float
    tolerance: float = 0.01


class GSSConfig(BaseModel):
    year: int
    landing_page: str
    terms: str = "norc_copyright_personal_use_only"
    redistributable: bool = False
    weight_column: str = "wtssps"
    benchmark: GSSBenchmark
    roles: list[str]


class GSSAdapter(SourceAdapter):
    slug = "gss"

    def __init__(self) -> None:
        self._client = httpx.Client(
            follow_redirects=True,
            timeout=120,
            headers={"User-Agent": "microdata-lab/1.0"},
        )
        config_path = Path(__file__).resolve().parents[3] / "config" / "gss" / "2024.yaml"
        with config_path.open() as f:
            self.definition = GSSConfig.model_validate(yaml.safe_load(f))

    def discover(self, year: int | None = None) -> DiscoveredRelease:
        yr = year or self.definition.year
        roles: list[DiscoveredArtifact] = [
            DiscoveredArtifact(
                role=DATA_STATA,
                url=_url_adapter.validate_strings(f"{BASE_URL}/{yr}_stata.zip"),
                link_text=f"GSS {yr} Stata",
                filename=f"{yr}_stata.zip",
                documentation=False,
            ),
            DiscoveredArtifact(
                role=CODEBOOK,
                url=_url_adapter.validate_strings(CODEBOOK_URL),
                link_text=f"GSS {yr} Codebook R3a",
                filename=f"GSS_{yr}_Codebook_R3a.pdf",
                documentation=True,
            ),
        ]
        return DiscoveredRelease(
            survey="gss",
            year=yr,
            landing_page=_url_adapter.validate_strings(self.definition.landing_page),
            artifacts=roles,
            source_metadata={
                "terms": self.definition.terms,
                "redistributable": self.definition.redistributable,
                "weight_column": self.definition.weight_column,
            },
        )

    def _read_dta(self, run_root: Path, artifacts: list[StoredArtifact]) -> pd.DataFrame:
        for a in artifacts:
            if str(a.role) == DATA_STATA:
                zip_path = run_root / a.relative_path
                with zip_path.open("rb") as f, zipfile.ZipFile(f) as zf:
                    dta_names = [n for n in zf.namelist() if n.endswith(".dta")]
                    if not dta_names:
                        raise ValueError("No .dta file found in GSS Stata zip")
                    with zf.open(dta_names[0]) as df_file:
                        return pd.read_stata(
                            io.BytesIO(df_file.read()),
                            convert_categoricals=False,
                        )
        raise ValueError("GSS Stata artifact not found")

    def validate_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> ValidationResult:
        checks: dict[str, bool] = {}
        notes: list[str] = []

        roles_present = {str(a.role) for a in artifacts}
        # Only check primary roles; documentation PDFs are bundled inside the Stata zip
        for role in ["stata_zip", "codebook_pdf"]:
            checks[f"gss_role_{role}_present"] = role in roles_present

        try:
            df = self._read_dta(run_root, artifacts)
            checks["gss_rows_present"] = len(df) > 0
            notes.append(f"rows={len(df)}")

            wt_col = self.definition.weight_column
            checks["gss_weight_column_present"] = wt_col in df.columns
            if wt_col in df.columns:
                weight = pd.to_numeric(df[wt_col], errors="coerce").fillna(0)
                checks["gss_weight_positive"] = weight.sum() > 0
                notes.append(f"weight_sum={weight.sum():.0f}")

                bm = self.definition.benchmark
                if bm.variable in df.columns:
                    var = pd.to_numeric(df[bm.variable], errors="coerce")
                    mask = var == 1
                    observed_share = weight[mask.fillna(False)].sum() / weight.sum()
                    checks["gss_benchmark_share_matches"] = (
                        abs(observed_share - bm.expected_share) <= bm.tolerance
                    )
                    notes.append(
                        f"benchmark_{bm.variable}_share={observed_share:.4f} "
                        f"expected={bm.expected_share} tol={bm.tolerance}"
                    )
                else:
                    checks["gss_benchmark_share_matches"] = False
                    notes.append(f"benchmark_variable_{bm.variable}_missing")
            else:
                checks["gss_weight_positive"] = False
                checks["gss_benchmark_share_matches"] = False

            checks["gss_year_matches"] = (
                "year" in df.columns and int(df["year"].iloc[0]) == release.year
            )
            checks["gss_terms_non_redistributable"] = not self.definition.redistributable
        except Exception as e:
            checks["gss_dta_readable"] = False
            notes.append(f"error={e}")

        return ValidationResult(
            passed=all(checks.values()),
            checks=checks,
            notes=notes,
        )

    def normalize_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> list[Path]:
        del release
        df = self._read_dta(run_root, artifacts)
        normalized = run_root / "normalized"
        normalized.mkdir(parents=True, exist_ok=True)
        output = normalized / "gss_2024.parquet"
        for col in df.columns:
            if df[col].dtype.name == "category":
                df[col] = df[col].astype(str)
        df.to_parquet(output, engine="pyarrow", compression="zstd")
        return [output]

    def download_client(self) -> httpx.Client:
        return self._client

    def close(self) -> None:
        self._client.close()
