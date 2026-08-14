from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pyarrow.parquet as pq
from pydantic import AnyHttpUrl, TypeAdapter

from microdata_lab.adapters.meps import MEPSAdapter, MEPSConfig
from microdata_lab.models import DiscoveredRelease, StoredArtifact

_url_adapter = TypeAdapter(AnyHttpUrl)
DATA_DTA = "data_dta"
DOCS_PDF = "docs_pdf"
CODEBOOK_PDF = "codebook_pdf"
SUMMARY_TXT = "summary_txt"


def _config() -> MEPSConfig:
    return MEPSConfig.model_validate(
        {
            "puf_id": "HC-251",
            "puf_number": "251",
            "year": 2023,
            "landing_page": "https://meps.ahrq.gov/mepsweb/data_stats/download_data_files_detail.jsp?cboPufNumber=HC-251",
            "data_base": "https://meps.ahrq.gov/mepsweb/data_files/pufs/h251",
            "docs_base": "https://meps.ahrq.gov/mepsweb/data_stats/download_data/pufs/h251",
            "weight_column": "PERWT23F",
            "expenditure_column": "TOTEXP23",
            "insurance_column": "INSCOV23",
            "benchmark": {
                "variable": "TOTEXP23",
                "weight": "PERWT23F",
                "expected_mean": 3230.77,
                "tolerance": 0.01,
                "description": "Weighted mean total health care expenditure per person, 2023",
            },
            "terms": "us_federal_public_domain",
        }
    )


def _adapter() -> MEPSAdapter:
    return MEPSAdapter(definition=_config())


def _make_dta_zip(tmp_path: Path) -> bytes:
    import pandas as pd

    df = pd.DataFrame(
        {
            "DUPERSID": ["P001", "P002", "P003", "P004"],
            "TOTEXP23": [1000.0, 5000.0, 20000.0, 0.0],
            "PERWT23F": [1000.0, 2000.0, 500.0, 3000.0],
            "INSCOV23": ["1 ANY PRIVATE", "2 PUBLIC ONLY", "1 ANY PRIVATE", "3 UNINSURED"],
            "SEX": [1, 2, 1, 2],
            "AGE31X": [25, 45, 65, 30],
        }
    )
    buf = io.BytesIO()
    df.to_stata(buf, write_index=False, version=118)
    buf.seek(0)

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("h251.dta", buf.getvalue())
    return zip_buf.getvalue()


def _store_artifacts(tmp_path: Path) -> list[StoredArtifact]:
    art_dir = tmp_path / "artifacts/data_dta"
    art_dir.mkdir(parents=True, exist_ok=True)
    dta_data = _make_dta_zip(tmp_path)
    (art_dir / "h251dta.zip").write_bytes(dta_data)

    docs_dir = tmp_path / "artifacts/docs_pdf"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "h251doc.pdf").write_bytes(b"%PDF-1.4 fake")

    return [
        StoredArtifact(
            role=DATA_DTA,
            source_url=_url_adapter.validate_python(
                "https://meps.ahrq.gov/mepsweb/data_files/pufs/h251/h251dta.zip"
            ),
            filename="h251dta.zip",
            relative_path="artifacts/data_dta/h251dta.zip",
            sha256="0" * 64,
            bytes=len(dta_data),
        ),
        StoredArtifact(
            role=DOCS_PDF,
            source_url=_url_adapter.validate_python(
                "https://meps.ahrq.gov/mepsweb/data_stats/download_data/pufs/h251/h251doc.pdf"
            ),
            filename="h251doc.pdf",
            relative_path="artifacts/docs_pdf/h251doc.pdf",
            sha256="0" * 64,
            bytes=14,
            documentation=True,
        ),
    ]


def _make_release() -> DiscoveredRelease:
    return DiscoveredRelease(
        survey="meps",
        year=2023,
        landing_page=_url_adapter.validate_python(
            "https://meps.ahrq.gov/mepsweb/data_stats/download_data_files_detail.jsp?cboPufNumber=HC-251"
        ),
        artifacts=[],
    )


def test_meps_discover() -> None:
    adapter = _adapter()
    release = adapter.discover()
    assert release.survey == "meps"
    assert release.year == 2023
    roles = [str(a.role) for a in release.artifacts]
    assert DATA_DTA in roles
    assert DOCS_PDF in roles
    assert CODEBOOK_PDF in roles
    adapter.close()


def test_meps_validate_passes(tmp_path: Path) -> None:
    adapter = _adapter()
    release = _make_release()
    artifacts = _store_artifacts(tmp_path)
    result = adapter.validate_release(tmp_path, release, artifacts)
    assert result.passed, f"Failed: {result.checks}, notes: {result.notes}"
    assert result.checks["meps_dta_file_present"]
    assert result.checks["meps_weight_column_present"]
    assert result.checks["meps_expenditure_column_present"]
    adapter.close()


def test_meps_normalize_creates_parquet(tmp_path: Path) -> None:
    adapter = _adapter()
    release = _make_release()
    artifacts = _store_artifacts(tmp_path)
    outputs = adapter.normalize_release(tmp_path, release, artifacts)
    assert len(outputs) == 1
    assert outputs[0].name == "meps_h251.parquet"
    meta = pq.ParquetFile(outputs[0]).metadata
    assert meta.num_rows == 4
    adapter.close()


def test_meps_public_domain_metadata() -> None:
    adapter = _adapter()
    release = adapter.discover()
    assert release.source_metadata["terms"] == "us_federal_public_domain"
    assert "public domain" in release.source_metadata["redistribution_note"]
    adapter.close()
