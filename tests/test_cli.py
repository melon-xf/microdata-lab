from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from microdata_lab.cli import app

runner = CliRunner()


def test_sources_command() -> None:
    result = runner.invoke(app, ["sources"])
    assert result.exit_code == 0
    assert "scf" in result.stdout.lower()


def test_status_handles_empty_root(tmp_path: Path) -> None:
    result = runner.invoke(app, ["status", "--data-root", str(tmp_path)])
    assert result.exit_code == 0
    assert "No promoted releases" in result.stdout
