from __future__ import annotations

import json
from pathlib import Path

from microdata_lab.catalog import rebuild_catalog, search_catalog


def test_catalog_indexes_variables_and_document_text(tmp_path: Path) -> None:
    release = tmp_path / "releases/scf/2022/abc"
    data = release / "extracted/summary_extract_csv"
    docs = release / "docs"
    data.mkdir(parents=True)
    docs.mkdir(parents=True)
    (data / "SCFP2022.csv").write_text("NETWORTH,CCBAL,WGT\n10,1,2\n")
    (docs / "codebook.md").write_text("Credit card balance is reported in CCBAL.\n")
    (release / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "survey": "scf",
                "year": 2022,
                "release_id": "scf-2022-abc",
                "landing_page": "https://example.com",
                "discovered_at": "2026-01-01T00:00:00Z",
                "retrieved_at": "2026-01-01T00:00:00Z",
                "release_sha256": "a" * 64,
                "artifacts": [],
                "validation": {"passed": True, "checks": {}, "notes": []},
            }
        )
    )
    current = tmp_path / "current"
    current.mkdir()
    (current / "scf.json").write_text(
        json.dumps({"release_path": str(release), "release_id": "scf-2022-abc"})
    )

    counts = rebuild_catalog(tmp_path)
    results = search_catalog(tmp_path, "credit card")

    assert counts.variables == 3
    assert counts.documents == 1
    assert any(result["kind"] == "document" for result in results)
