from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from microdata_lab.storage import UnsafeArchiveError, safe_extract_zip


def test_extracts_normal_zip(tmp_path: Path) -> None:
    archive = tmp_path / "good.zip"
    destination = tmp_path / "out"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("nested/data.csv", "x,y\n1,2\n")

    extracted = safe_extract_zip(archive, destination)

    assert extracted == [destination / "nested/data.csv"]
    assert extracted[0].read_text() == "x,y\n1,2\n"


def test_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../escape.txt", "no")

    with pytest.raises(UnsafeArchiveError):
        safe_extract_zip(archive, tmp_path / "out")

    assert not (tmp_path / "escape.txt").exists()
