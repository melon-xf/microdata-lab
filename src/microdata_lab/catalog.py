from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from microdata_lab.config import initialize_data_root

_LOCK_RETRIES = 5
_LOCK_RETRY_DELAY = 1.0


@dataclass(frozen=True)
class CatalogCounts:
    releases: int
    variables: int
    documents: int


def _connect_with_lock_retry(database: Path) -> duckdb.DuckDBPyConnection:
    """Connect to the DuckDB catalog, retrying when another process holds the lock."""
    for attempt in range(_LOCK_RETRIES):
        try:
            return duckdb.connect(str(database))
        except duckdb.IOException as error:
            if "lock" not in str(error).lower() or attempt == _LOCK_RETRIES - 1:
                raise
            time.sleep(_LOCK_RETRY_DELAY * (attempt + 1))
    raise RuntimeError("Could not acquire the catalog lock")  # pragma: no cover


def rebuild_catalog(data_root: Path) -> CatalogCounts:
    initialize_data_root(data_root)
    database = data_root / "catalog" / "catalog.duckdb"
    connection = _connect_with_lock_retry(database)
    try:
        _reset_schema(connection)
        release_count = variable_count = document_count = 0
        for pointer_path in sorted((data_root / "current").glob("*.json")):
            pointer = json.loads(pointer_path.read_text())
            release_root = Path(pointer["release_path"])
            manifest = json.loads((release_root / "manifest.json").read_text())
            survey = str(manifest["survey"])
            year = int(manifest["year"])
            release_id = str(manifest["release_id"])
            connection.execute(
                "INSERT INTO releases VALUES (?, ?, ?, ?, ?)",
                [
                    survey,
                    year,
                    release_id,
                    str(release_root),
                    str(manifest["release_sha256"]),
                ],
            )
            release_count += 1

            normalized = [
                release_root / asset["relative_path"]
                for asset in manifest.get("normalized_assets", [])
            ]
            data_files = normalized or sorted((release_root / "extracted").rglob("*.csv"))
            for data_path in data_files:
                schema = (
                    pq.read_schema(data_path)
                    if data_path.suffix.lower() == ".parquet"
                    else pacsv.open_csv(data_path).schema
                )
                for name, data_type in zip(schema.names, schema.types, strict=True):
                    connection.execute(
                        "INSERT INTO variables VALUES (?, ?, ?, ?, ?, ?)",
                        [
                            survey,
                            year,
                            release_id,
                            str(data_path.relative_to(release_root)),
                            name,
                            str(data_type),
                        ],
                    )
                    variable_count += 1

            docs_root = release_root / "docs"
            if docs_root.exists():
                for markdown in sorted(docs_root.glob("*.md")):
                    connection.execute(
                        "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?)",
                        [
                            survey,
                            year,
                            release_id,
                            markdown.stem,
                            str(markdown.relative_to(release_root)),
                            markdown.read_text(errors="replace"),
                        ],
                    )
                    document_count += 1
        connection.commit()
        return CatalogCounts(release_count, variable_count, document_count)
    finally:
        connection.close()


def search_catalog(data_root: Path, query: str, limit: int = 20) -> list[dict[str, Any]]:
    database = data_root / "catalog" / "catalog.duckdb"
    if not database.exists():
        return []
    needle = f"%{query.lower()}%"
    connection = duckdb.connect(str(database), read_only=True)
    try:
        variable_rows = connection.execute(
            """
            SELECT survey, year, release_id, variable_name, data_type, source_file
            FROM variables
            WHERE lower(variable_name) LIKE ?
            ORDER BY survey, year DESC, variable_name
            LIMIT ?
            """,
            [needle, limit],
        ).fetchall()
        remaining = max(0, limit - len(variable_rows))
        document_rows = connection.execute(
            """
            SELECT survey, year, release_id, document_role, source_file,
                   substr(content, greatest(1, strpos(lower(content), lower(?)) - 160), 420)
            FROM documents
            WHERE lower(content) LIKE ?
            ORDER BY survey, year DESC, document_role
            LIMIT ?
            """,
            [query, needle, remaining],
        ).fetchall()
    finally:
        connection.close()

    results: list[dict[str, Any]] = []
    for survey, year, release_id, name, data_type, source_file in variable_rows:
        results.append(
            {
                "kind": "variable",
                "survey": survey,
                "year": year,
                "release_id": release_id,
                "name": name,
                "data_type": data_type,
                "source_file": source_file,
            }
        )
    for survey, year, release_id, role, source_file, snippet in document_rows:
        results.append(
            {
                "kind": "document",
                "survey": survey,
                "year": year,
                "release_id": release_id,
                "role": role,
                "source_file": source_file,
                "snippet": " ".join(str(snippet).split()),
            }
        )
    return results


def _reset_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("DROP TABLE IF EXISTS documents")
    connection.execute("DROP TABLE IF EXISTS variables")
    connection.execute("DROP TABLE IF EXISTS releases")
    connection.execute(
        """
        CREATE TABLE releases (
            survey VARCHAR,
            year INTEGER,
            release_id VARCHAR,
            release_path VARCHAR,
            release_sha256 VARCHAR
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE variables (
            survey VARCHAR,
            year INTEGER,
            release_id VARCHAR,
            source_file VARCHAR,
            variable_name VARCHAR,
            data_type VARCHAR
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE documents (
            survey VARCHAR,
            year INTEGER,
            release_id VARCHAR,
            document_role VARCHAR,
            source_file VARCHAR,
            content VARCHAR
        )
        """
    )
