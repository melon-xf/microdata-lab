"""Doctor and scaffold command tests. Everything is mocked: no network."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from typer.testing import CliRunner

from microdata_lab import cli
from microdata_lab.cli import app
from microdata_lab.visualization import ChartConfig

runner = CliRunner()


# --- individual check helpers ------------------------------------------------


def test_check_data_root_pass_and_fail(tmp_path: Path) -> None:
    name, ok, _ = cli._check_data_root(tmp_path)
    assert ok and name == "MICRODATA_ROOT"

    _, ok, detail = cli._check_data_root(tmp_path / "missing")
    assert not ok and "does not exist" in detail

    not_a_dir = tmp_path / "file"
    not_a_dir.write_text("x")
    _, ok, detail = cli._check_data_root(not_a_dir)
    assert not ok and "not a directory" in detail


def test_check_env_keys_names_only(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {"BLS_USER_AGENT": "secret-ua", "FRED_API_KEY": "secret-key"}
    monkeypatch.setattr(cli, "read_runtime_value", lambda name: values.get(name))
    _, ok, detail = cli._check_env_keys(("BLS_USER_AGENT", "FRED_API_KEY", "CENSUS_API_KEY"))
    assert not ok
    assert "CENSUS_API_KEY" in detail
    # Values must never appear in output.
    assert "secret-ua" not in detail and "secret-key" not in detail

    _, ok, detail = cli._check_env_keys(("BLS_USER_AGENT", "FRED_API_KEY"))
    assert ok and "BLS_USER_AGENT" in detail and "secret" not in detail


def test_check_rscript(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, ok, detail = cli._check_rscript(tmp_path)
    assert not ok and "not found" in detail

    rscript = tmp_path / ".r-env" / "bin" / "Rscript"
    rscript.parent.mkdir(parents=True)
    rscript.write_text("#!/bin/sh\n")

    def fake_run_ok(*args: object, **kwargs: object):
        return SimpleNamespace(returncode=0, stdout="R version 4.5.1 (2025-06-13)\n", stderr="")

    monkeypatch.setattr(cli.subprocess, "run", fake_run_ok)
    _, ok, detail = cli._check_rscript(tmp_path)
    assert ok and "R version 4.5.1" in detail

    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="boom"),
    )
    _, ok, _ = cli._check_rscript(tmp_path)
    assert not ok

    def _timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd="Rscript", timeout=30)

    monkeypatch.setattr(cli.subprocess, "run", _timeout)
    _, ok, _ = cli._check_rscript(tmp_path)
    assert not ok


def test_check_playwright(tmp_path: Path) -> None:
    _, ok, detail = cli._check_playwright(tmp_path)
    assert not ok and "playwright install" in detail

    cache = tmp_path / ".cache" / "ms-playwright"
    cache.mkdir(parents=True)
    _, ok, _ = cli._check_playwright(tmp_path)
    assert not ok

    (cache / "chromium-1234").mkdir()
    _, ok, detail = cli._check_playwright(tmp_path)
    assert ok and "chromium" in detail


class _FakeResponse:
    def __init__(self, status_code: int, content: bytes, payload: dict | None = None) -> None:
        self.status_code = status_code
        self.content = content
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.closed = False

    def get(self, *args, **kwargs) -> _FakeResponse:
        return self._response

    def close(self) -> None:
        self.closed = True


def test_check_bls_reachable_pass_block_and_error() -> None:
    ok_response = _FakeResponse(200, b"series_id        \tarea_code\titem_code\n")
    _, ok, detail = cli._check_bls_reachable(lambda: _FakeClient(ok_response))
    assert ok

    block_payload = b'<!DOCTYPE HTML>\n<html lang="en-us"><title>Access Denied</title>'
    block = _FakeResponse(403, block_payload)
    _, ok, detail = cli._check_bls_reachable(lambda: _FakeClient(block))
    assert not ok and "BLS_USER_AGENT" in detail

    _, ok, detail = cli._check_bls_reachable(
        lambda: (_ for _ in ()).throw(RuntimeError("Missing required secret BLS_USER_AGENT"))
    )
    assert not ok and "BLS_USER_AGENT" in detail


def test_check_fred_ping() -> None:
    good = _FakeClient(_FakeResponse(200, b"{}", {"seriess": [{"id": "GNPCA"}]}))
    _, ok, detail = cli._check_fred_ping(api_key="fake-key", client=good)
    assert ok and "GNPCA" in detail

    bad_payload = {"error_code": 400, "error_message": "Bad API key"}
    bad = _FakeClient(_FakeResponse(400, b"{}", bad_payload))
    _, ok, detail = cli._check_fred_ping(api_key="fake-key", client=bad)
    assert not ok and "fake-key" not in detail


# --- commands ------------------------------------------------------------------

_PASS = ("check", True, "ok")


def _patch_doctor(monkeypatch: pytest.MonkeyPatch, fail: str | None = None) -> None:
    helpers = {
        "_check_data_root": cli._check_data_root,
        "_check_env_keys": cli._check_env_keys,
        "_check_rscript": cli._check_rscript,
        "_check_playwright": cli._check_playwright,
        "_check_bls_reachable": cli._check_bls_reachable,
        "_check_fred_ping": cli._check_fred_ping,
    }
    for name in helpers:
        def fake(*args, _name=name, **kwargs):
            if _name == fail:
                return ("failing check", False, "remediation hint")
            return _PASS

        monkeypatch.setattr(cli, name, fake)


def test_doctor_command_all_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_doctor(monkeypatch)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "All doctor checks passed" in result.stdout


def test_doctor_command_fails_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_doctor(monkeypatch, fail="_check_fred_ping")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "FAIL" in result.stdout
    assert "remediation hint" in result.stdout


def test_new_scaffolds_contract_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["new", "_smoke_test_slug"])
    assert result.exit_code == 0
    target = tmp_path / "analyses" / "_smoke_test_slug"

    question = (target / "question.md").read_text()
    for heading in ("Estimand", "Universe", "Design", "Release IDs"):
        assert heading in question

    estimate = (target / "estimate.py").read_text()
    assert "from microdata_lab" in estimate
    compile(estimate, "estimate.py", "exec")

    chart = yaml.safe_load((target / "chart.yaml").read_text())
    ChartConfig.model_validate(chart)

    readme = (target / "README.md").read_text()
    assert "Generated by `microdata new" in readme


def test_new_refuses_to_clobber(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["new", "_smoke_test_slug"]).exit_code == 0
    sentinel = tmp_path / "analyses" / "_smoke_test_slug" / "question.md"
    sentinel.write_text("hand-edited")
    result = runner.invoke(app, ["new", "_smoke_test_slug"])
    assert result.exit_code == 1
    assert "Refusing to clobber" in result.stdout
    assert sentinel.read_text() == "hand-edited"


def test_new_rejects_bad_slug(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["new", "Bad Slug!"])
    assert result.exit_code != 0
    assert not (tmp_path / "analyses").exists()
