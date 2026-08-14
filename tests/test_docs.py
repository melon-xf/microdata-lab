from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from microdata_lab import docs


def test_ipums_cbk_is_extracted_as_direct_text(tmp_path: Path) -> None:
    source = tmp_path / "extract.cbk"
    source.write_text("IPUMS codebook\nYEAR  Survey year\n")

    text, method = docs._extract_text(source)

    assert text == "IPUMS codebook\nYEAR  Survey year\n"
    assert method == "direct-text"


def test_html_extraction_keeps_main_text_and_removes_navigation(tmp_path: Path) -> None:
    source = tmp_path / "guide.html"
    source.write_text(
        "<html><body><nav>Site navigation</nav><main><h1>Method</h1>"
        "<p>Use the official weight.</p><script>bad()</script></main></body></html>"
    )

    text, method = docs._extract_text(source)

    assert text == "Method\nUse the official weight."
    assert method == "selectolax-html"


def test_pdf_extraction_uses_configured_executable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    executable = tmp_path / "pdftotext"
    executable.write_text("#!/bin/sh\n")
    executable.chmod(0o755)
    source = tmp_path / "methodology.pdf"
    source.write_bytes(b"fixture")
    captured: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        captured.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=b"page one\fpage two")

    monkeypatch.setenv("MICRODATA_PDFTOTEXT", str(executable))
    monkeypatch.setattr(docs.subprocess, "run", fake_run)

    text, method = docs._extract_text(source)

    assert text == "page one\fpage two"
    assert method == "pdftotext-layout"
    assert captured[0][0] == str(executable.resolve())


def test_invalid_configured_pdftotext_fails_visibly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing = tmp_path / "missing"
    monkeypatch.setenv("MICRODATA_PDFTOTEXT", str(missing))

    with pytest.raises(RuntimeError, match="not executable"):
        docs._resolve_pdftotext()
