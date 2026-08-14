from __future__ import annotations

import io
import zipfile
from pathlib import Path

import httpx
import pandas as pd
import yaml
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, TypeAdapter

from microdata_lab.adapters.base import SourceAdapter
from microdata_lab.models import (
    DiscoveredArtifact,
    DiscoveredRelease,
    StoredArtifact,
    ValidationResult,
)

DEFINITION_PATH = Path(__file__).resolve().parents[3] / "config/meps/2023.yaml"
_url_adapter = TypeAdapter(AnyHttpUrl)

DATA_DTA = "data_dta"
DATA_DAT = "data_dat"
DATA_SSP = "data_ssp"
DOCS_PDF = "docs_pdf"
CODEBOOK_PDF = "codebook_pdf"
SUMMARY_TXT = "summary_txt"
PUF_DETAIL = "puf_detail"


class MEPSBenchmark(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variable: str
    weight: str
    expected_mean: float
    tolerance: float
    description: str


class MEPSConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    puf_id: str
    puf_number: str
    year: int
    landing_page: AnyHttpUrl
    data_base: AnyHttpUrl
    docs_base: AnyHttpUrl
    weight_column: str
    expenditure_column: str
    insurance_column: str
    benchmark: MEPSBenchmark
    terms: str = "us_federal_public_domain"


class MEPSAdapter(SourceAdapter):
    slug = "meps"

    def __init__(
        self,
        *,
        definition: MEPSConfig | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.definition = definition or _load_definition(DEFINITION_PATH)
        self._client = client

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                follow_redirects=True,
                timeout=120,
                headers={"User-Agent": "microdata-lab/1.0"},
            )
        return self._client

    def available_years(self) -> list[int]:
        return [self.definition.year]

    def discover(self, year: int | None = None) -> DiscoveredRelease:
        selected_year = year or self.definition.year
        pn = self.definition.puf_number
        db = str(self.definition.data_base).rstrip("/")
        docb = str(self.definition.docs_base).rstrip("/")

        artifacts = [
            DiscoveredArtifact(
                role=DATA_DTA,
                url=_url_adapter.validate_python(f"{db}/h{pn}dta.zip"),
                filename=f"h{pn}dta.zip",
                link_text=f"MEPS {self.definition.puf_id} Stata data file",
            ),
            DiscoveredArtifact(
                role=DOCS_PDF,
                url=_url_adapter.validate_python(f"{docb}/h{pn}doc.pdf"),
                filename=f"h{pn}doc.pdf",
                link_text=f"MEPS {self.definition.puf_id} documentation",
                documentation=True,
            ),
            DiscoveredArtifact(
                role=CODEBOOK_PDF,
                url=_url_adapter.validate_python(f"{docb}/h{pn}cb.pdf"),
                filename=f"h{pn}cb.pdf",
                link_text=f"MEPS {self.definition.puf_id} codebook",
                documentation=True,
            ),
            DiscoveredArtifact(
                role=SUMMARY_TXT,
                url=_url_adapter.validate_python(f"{docb}/h{pn}su.txt"),
                filename=f"h{pn}su.txt",
                link_text=f"MEPS {self.definition.puf_id} SAS usage file",
                documentation=True,
            ),
        ]

        return DiscoveredRelease(
            survey=self.slug,
            year=selected_year,
            landing_page=self.definition.landing_page,
            artifacts=artifacts,
            source_metadata={
                "record_unit": "person",
                "puf_id": self.definition.puf_id,
                "weight_column": self.definition.weight_column,
                "expenditure_column": self.definition.expenditure_column,
                "insurance_column": self.definition.insurance_column,
                "terms": self.definition.terms,
                "redistribution_note": (
                    "MEPS is produced by AHRQ (U.S. HHS). "
                    "U.S. federal government works are in the public domain (17 USC 105)."
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

        dta_path = _artifact_path(artifacts, DATA_DTA, run_root)
        with dta_path.open("rb") as f, zipfile.ZipFile(f) as zf:
            dta_names = [n for n in zf.namelist() if n.endswith(".dta")]
            if not dta_names:
                checks["meps_dta_file_present"] = False
                return ValidationResult(passed=False, checks=checks, notes=notes)
            with zf.open(dta_names[0]) as df_file:
                df = pd.read_stata(io.BytesIO(df_file.read()))

        checks["meps_dta_file_present"] = True
        checks["meps_rows_present"] = len(df) > 0
        notes.append(f"rows={len(df)}")
        notes.append(f"columns={len(df.columns)}")

        wt_col = self.definition.weight_column
        exp_col = self.definition.expenditure_column

        checks["meps_weight_column_present"] = wt_col in df.columns
        checks["meps_expenditure_column_present"] = exp_col in df.columns

        if wt_col in df.columns and exp_col in df.columns:
            w = pd.to_numeric(df[wt_col], errors="coerce")
            v = pd.to_numeric(df[exp_col], errors="coerce")
            wmean = float((v * w).sum() / w.sum())
            notes.append(f"weighted_mean_{exp_col}={wmean:.2f}")

            bm = self.definition.benchmark
            checks["meps_benchmark_mean_matches"] = abs(wmean - bm.expected_mean) <= bm.tolerance
            notes.append(f"benchmark_expected={bm.expected_mean} tolerance={bm.tolerance}")

            pop = float(w.sum())
            notes.append(f"weighted_population={pop:.0f}")
            checks["meps_population_positive"] = pop > 0

        ins_col = self.definition.insurance_column
        if ins_col in df.columns:
            ins_counts = df[ins_col].value_counts().to_dict()
            notes.append(f"insurance_coverage={ins_counts}")
            checks["meps_insurance_column_present"] = True
        else:
            checks["meps_insurance_column_present"] = False

        checks["meps_docs_present"] = any(str(a.role) == DOCS_PDF for a in artifacts)

        return ValidationResult(passed=all(checks.values()), checks=checks, notes=notes)

    def normalize_release(
        self,
        run_root: Path,
        release: DiscoveredRelease,
        artifacts: list[StoredArtifact],
    ) -> list[Path]:
        del release
        dta_path = _artifact_path(artifacts, DATA_DTA, run_root)
        with dta_path.open("rb") as f, zipfile.ZipFile(f) as zf:
            dta_names = [n for n in zf.namelist() if n.endswith(".dta")]
            if not dta_names:
                return []
            with zf.open(dta_names[0]) as df_file:
                df = pd.read_stata(io.BytesIO(df_file.read()))

        # Convert categorical columns (from Stata value labels) to strings
        # so PyArrow can serialize them to Parquet
        for col in df.columns:
            if df[col].dtype.name == "category":
                df[col] = df[col].astype(str)

        normalized = run_root / "normalized"
        normalized.mkdir(parents=True, exist_ok=True)
        output = normalized / f"meps_h{self.definition.puf_number}.parquet"
        df.to_parquet(output, engine="pyarrow", compression="zstd")
        return [output]

    def download_client(self) -> httpx.Client:
        return self.client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()


def _load_definition(path: Path) -> MEPSConfig:
    with path.open() as handle:
        return MEPSConfig.model_validate(yaml.safe_load(handle))


def _artifact_path(artifacts: list[StoredArtifact], role: str, run_root: Path) -> Path:
    matches = [a for a in artifacts if str(a.role) == role]
    if len(matches) != 1:
        raise ValueError(f"Expected one {role} artifact, found {len(matches)}")
    return run_root / matches[0].relative_path
