from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from selectolax.parser import HTMLParser

from microdata_lab.models import ArtifactRole, StoredArtifact

_DOCUMENT_ROLES = {
    ArtifactRole.CODEBOOK,
    ArtifactRole.STANDARD_ERROR_DOCUMENTATION,
    ArtifactRole.CHANGES,
    ArtifactRole.VARIABLE_DEFINITIONS,
}


def build_document_sidecars(run_root: Path, artifacts: list[StoredArtifact]) -> None:
    docs_root = run_root / "docs"
    docs_root.mkdir(parents=True, exist_ok=True)
    for artifact in artifacts:
        if not artifact.documentation and artifact.role not in _DOCUMENT_ROLES:
            continue
        source = run_root / artifact.relative_path
        markdown = docs_root / f"{artifact.role}.md"
        text, extraction_method = _extract_text(source)
        pages = text.split("\f")
        body_parts = []
        for page_number, page in enumerate(pages, start=1):
            cleaned = page.strip()
            if cleaned:
                body_parts.append(f"<!-- source-page: {page_number} -->\n\n{cleaned}")
        header = (
            "---\n"
            f"role: {artifact.role}\n"
            f"source_file: {artifact.filename}\n"
            f"source_sha256: {artifact.sha256}\n"
            f"extraction_method: {extraction_method}\n"
            "---\n\n"
        )
        markdown.write_text(header + "\n\n".join(body_parts) + "\n", errors="strict")
        metadata = {
            "role": str(artifact.role),
            "source_file": artifact.filename,
            "source_sha256": artifact.sha256,
            "extraction_method": extraction_method,
            "page_segments": len(body_parts),
        }
        (docs_root / f"{artifact.role}.extraction.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n"
        )


def _extract_text(source: Path) -> tuple[str, str]:
    suffix = source.suffix.lower()
    if suffix == ".zip":
        # Some codebooks ship as a zip wrapping a single HTML report.
        import zipfile

        with zipfile.ZipFile(source) as bundle:
            html_members = [n for n in bundle.namelist() if n.lower().endswith((".html", ".htm"))]
            if len(html_members) != 1:
                raise ValueError(f"Documentation zip must wrap exactly one HTML file: {source}")
            text, method = _extract_html(bundle.read(html_members[0]))
            return text, f"{method}-zipped"
    if suffix in {".txt", ".csv", ".md", ".cbk"}:
        return source.read_text(errors="replace"), "direct-text"
    if suffix in {".htm", ".html"}:
        return _extract_html(source.read_bytes())
    if suffix == ".pdf":
        executable = _resolve_pdftotext()
        if executable is None:
            raise RuntimeError("pdftotext is required to convert official PDF documentation")
        completed = subprocess.run(
            [executable, "-layout", str(source), "-"],
            check=True,
            capture_output=True,
        )
        return completed.stdout.decode("utf-8", errors="replace"), "pdftotext-layout"
    raise ValueError(f"Unsupported documentation format: {source}")


def _extract_html(raw: bytes) -> tuple[str, str]:
    tree = HTMLParser(raw.decode(errors="replace"))
    for selector in ("script", "style", "noscript", "nav", "header", "footer"):
        for node in tree.css(selector):
            node.decompose()
    content = tree.css_first("main") or tree.css_first("article") or tree.body
    if content is None:
        raise ValueError("HTML documentation has no readable body")
    lines = [line.strip() for line in content.text(separator="\n").splitlines()]
    text = "\n".join(line for line in lines if line)
    if not text:
        raise ValueError("HTML documentation has no readable text")
    return text, "selectolax-html"


def _resolve_pdftotext() -> str | None:
    configured = os.environ.get("MICRODATA_PDFTOTEXT")
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate.resolve())
        raise RuntimeError(f"MICRODATA_PDFTOTEXT is not executable: {candidate}")
    system = shutil.which("pdftotext")
    if system:
        return system
    local = Path(__file__).resolve().parents[2] / ".r-env/bin/pdftotext"
    return str(local) if local.is_file() and os.access(local, os.X_OK) else None
