from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq
from pydantic import AnyHttpUrl, TypeAdapter

from microdata_lab.adapters.ilo import IloAdapter, IloConfig
from microdata_lab.models import StoredArtifact

_url_adapter = TypeAdapter(AnyHttpUrl)
DATA_JSON = "data_json"


def _adapter(tmp_path: Path) -> IloAdapter:
    cfg = IloConfig.model_validate(
        {
            "indicator_id": "SDG_0852_SEX_AGE_RT_A",
            "indicator_code": "SDG_0852_SEX_AGE_RT",
            "indicator_title": "Unemployment rate by sex and age (%)",
            "indicator_url": "https://ilostat.ilo.org/data/",
            "landing_page": "https://ilostat.ilo.org/data/",
            "reference_year": 2023,
            "benchmark": {
                "ref_area": "USA",
                "sex": "SEX_T",
                "classif1": "AGE_YTHADULT_YGE15",
                "expected_value": 3.638,
                "tolerance": 0.01,
            },
            "terms": "ilo_non_commercial_attribution",
            "record_unit": "country_year_observation",
        }
    )
    return IloAdapter(definition=cfg)


def _make_release(tmp_path: Path) -> tuple[Path, list[StoredArtifact]]:
    run_root = tmp_path / "run"
    rows = [
        {
            "ref_area": "USA",
            "source": "BA:453",
            "indicator": "SDG_0852_SEX_AGE_RT",
            "sex": "SEX_T",
            "classif1": "AGE_YTHADULT_YGE15",
            "time": "2023",
            "obs_value": 3.638,
        },
        {
            "ref_area": "USA",
            "source": "BA:453",
            "indicator": "SDG_0852_SEX_AGE_RT",
            "sex": "SEX_T",
            "classif1": "AGE_YTHADULT_YGE15",
            "time": "2022",
            "obs_value": 3.65,
        },
    ]
    rel = "artifacts/data_json/ilo_SDG_0852_SEX_AGE_RT_2023.json"
    (run_root / rel).parent.mkdir(parents=True, exist_ok=True)
    (run_root / rel).write_text(json.dumps(rows))
    artifacts = [
        StoredArtifact(
            role=DATA_JSON,
            source_url=_url_adapter.validate_python(
                "https://rplumber.ilo.org/data/indicator?id=SDG_0852_SEX_AGE_RT_A&format=.json"
            ),
            filename="ilo_SDG_0852_SEX_AGE_RT_2023.json",
            relative_path=rel,
            sha256="0" * 64,
            bytes=len(json.dumps(rows)),
        )
    ]
    return run_root, artifacts


def test_ilo_discover(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    try:
        release = adapter.discover()
        assert release.survey == "ilo"
        assert release.year == 2023
        assert len(release.artifacts) == 1
        assert "format=.json" in str(release.artifacts[0].url)
    finally:
        adapter.close()


def test_ilo_validate_benchmark_passes(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    try:
        run_root, artifacts = _make_release(tmp_path)
        release = adapter.discover()
        result = adapter.validate_release(run_root, release, artifacts)
        assert result.passed is True
        assert result.checks["ilo_benchmark"] is True
    finally:
        adapter.close()


def test_ilo_validate_fails_on_wrong_value(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    try:
        run_root, artifacts = _make_release(tmp_path)
        p = run_root / artifacts[0].relative_path
        rows = json.loads(p.read_text())
        rows[0]["obs_value"] = 9.9
        p.write_text(json.dumps(rows))
        release = adapter.discover()
        result = adapter.validate_release(run_root, release, artifacts)
        assert result.passed is False
        assert result.checks["ilo_benchmark"] is False
    finally:
        adapter.close()


def test_ilo_normalize_writes_parquet(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    try:
        run_root, artifacts = _make_release(tmp_path)
        release = adapter.discover()
        paths = adapter.normalize_release(run_root, release, artifacts)
        assert len(paths) == 1
        pf = pq.ParquetFile(paths[0])
        assert pf.metadata.num_rows == 2
    finally:
        adapter.close()
