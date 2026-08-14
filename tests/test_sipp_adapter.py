from __future__ import annotations

import json
from pathlib import Path

import httpx
import pandas as pd
import pyarrow.parquet as pq
from pydantic import AnyHttpUrl, TypeAdapter

from microdata_lab.adapters.sipp import (
    CODEBOOK,
    INPUT_EXAMPLE,
    PRIMARY_DATA,
    PRIMARY_SCHEMA,
    PRIMARY_VALIDATION,
    RELEASE_NOTES,
    REPLICATE_SCHEMA,
    REPLICATE_VALIDATION,
    REPLICATE_WEIGHTS,
    USERS_GUIDE,
    SIPPAdapter,
    SIPPBenchmarkDefinition,
    SIPPReleaseDefinition,
    SIPPWeightContract,
)
from microdata_lab.models import ArtifactRole, DiscoveredRelease, StoredArtifact

_HTTP_URL = TypeAdapter(AnyHttpUrl)


def _definition() -> SIPPReleaseDefinition:
    return SIPPReleaseDefinition(
        year=2025,
        landing_page=_HTTP_URL.validate_python("https://www.census.gov/sipp/2025.html"),
        users_guide_url=_HTTP_URL.validate_python(
            "https://www2.census.gov/sipp/2025_SIPP_Users_Guide.pdf"
        ),
        required_roles=[
            PRIMARY_DATA,
            PRIMARY_SCHEMA,
            PRIMARY_VALIDATION,
            REPLICATE_WEIGHTS,
            REPLICATE_SCHEMA,
            REPLICATE_VALIDATION,
            CODEBOOK,
            RELEASE_NOTES,
            INPUT_EXAMPLE,
        ],
        expected_primary_rows=4,
        expected_primary_columns=8,
        expected_replicate_rows=3,
        expected_replicate_columns=6,
        expected_weight_columns=3,
        expected_positive_weight_rows=3,
        expected_panel_min=2025,
        expected_months=[1, 2],
        benchmark=SIPPBenchmarkDefinition(
            variable="TPTOTINC",
            expected_nonmissing=3,
            expected_mean=3.0,
            absolute_tolerance=0.000001,
            validation_workbook_mean=3.0,
        ),
        weight_contract=SIPPWeightContract(
            primary="WPFINWGT",
            replicate_full_sample="REPWGT0",
            replicate_prefix="REPWGT",
            variance_replicates=2,
            fay_adjustment=0.5,
            expected_primary_mean=15.0,
            expected_replicate_mean=20.0,
            mean_tolerance=0.000001,
        ),
    )


def _role_value(role: ArtifactRole | str) -> str:
    return role.value if isinstance(role, ArtifactRole) else role


def test_sipp_discovers_exact_official_artifact_set() -> None:
    links = [
        "pu2025_csv.zip",
        "pu2025_schema.json",
        "pu2025_validate.xlsx",
        "rw2025_csv.zip",
        "rw2025_schema.json",
        "rw2025_validate.xlsx",
        "2025_SIPP_Data_Dictionary.pdf",
        "2025_SIPP_Release_Notes.pdf",
        "2025_sipp_python_input_example.py",
    ]
    html = "".join(f'<a href="https://www2.census.gov/2025/{name}">{name}</a>' for name in links)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, text=html)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        adapter = SIPPAdapter(definition=_definition(), client=client)
        assert adapter.available_years() == [2025]
        release = adapter.discover(2025)

    roles = {_role_value(artifact.role) for artifact in release.artifacts}
    assert roles == set(_definition().required_roles) | {USERS_GUIDE}
    assert all("census.gov" in str(artifact.url) for artifact in release.artifacts)


def test_sipp_validates_official_contract_and_normalizes(tmp_path: Path) -> None:
    definition = _definition()
    release, artifacts = _write_fixture(tmp_path, definition)
    adapter = SIPPAdapter(definition=definition, client=httpx.Client())
    try:
        validation = adapter.validate_release(tmp_path, release, artifacts)
        normalized = adapter.normalize_release(tmp_path, release, artifacts)
    finally:
        adapter.close()

    assert validation.passed, validation.checks
    assert all(validation.checks.values())
    assert len(normalized) == 2
    assert pq.ParquetFile(normalized[0]).metadata.num_rows == 4
    assert pq.ParquetFile(normalized[1]).metadata.num_rows == 3


def test_sipp_rejects_repwgt0_that_differs_from_primary_weight(tmp_path: Path) -> None:
    definition = _definition()
    release, artifacts = _write_fixture(tmp_path, definition, mismatched_full_weight=True)
    adapter = SIPPAdapter(definition=definition, client=httpx.Client())
    try:
        validation = adapter.validate_release(tmp_path, release, artifacts)
    finally:
        adapter.close()

    assert not validation.passed
    assert not validation.checks["sipp_repwgt0_matches_primary_weight"]


def _write_fixture(
    root: Path,
    definition: SIPPReleaseDefinition,
    *,
    mismatched_full_weight: bool = False,
) -> tuple[DiscoveredRelease, list[StoredArtifact]]:
    primary = pd.DataFrame(
        {
            "SSUID": ["A", "A", "B", "B"],
            "PNUM": [101, 101, 101, 101],
            "MONTHCODE": [1, 2, 1, 2],
            "SPANEL": [2025] * 4,
            "SWAVE": [1] * 4,
            "RIN_UNIV": [1, 1, 2, 1],
            "WPFINWGT": [10.0, 20.0, 0.0, 30.0],
            "TPTOTINC": [1.0, 3.0, None, 5.0],
        }
    )
    replicate = pd.DataFrame(
        {
            "SSUID": ["A", "A", "B"],
            "PNUM": [101, 101, 101],
            "MONTHCODE": [1, 2, 2],
            "REPWGT0": [11.0 if mismatched_full_weight else 10.0, 20.0, 30.0],
            "REPWGT1": [9.0, 22.0, 28.0],
            "REPWGT2": [12.0, 18.0, 31.0],
        }
    )
    primary_relative = "extracted/primary_data/pu2025.csv"
    replicate_relative = "extracted/replicate_weights/rw2025.csv"
    (root / primary_relative).parent.mkdir(parents=True)
    (root / replicate_relative).parent.mkdir(parents=True)
    primary.to_csv(root / primary_relative, sep="|", index=False)
    replicate.rename(columns=str.lower).to_csv(
        root / replicate_relative,
        sep="|",
        index=False,
    )

    primary_schema = _schema_for(primary)
    replicate_schema = _schema_for(replicate)
    stored_paths = {
        PRIMARY_SCHEMA: "artifacts/pu2025_schema.json",
        REPLICATE_SCHEMA: "artifacts/rw2025_schema.json",
        PRIMARY_VALIDATION: "artifacts/pu2025_validate.xlsx",
        REPLICATE_VALIDATION: "artifacts/rw2025_validate.xlsx",
    }
    (root / "artifacts").mkdir(parents=True)
    (root / stored_paths[PRIMARY_SCHEMA]).write_text(json.dumps(primary_schema))
    (root / stored_paths[REPLICATE_SCHEMA]).write_text(json.dumps(replicate_schema))
    pd.DataFrame(
        [
            {"Variable": "SPANEL", "N": 4, "N Miss": 0, "Mean": 2025.0},
            {"Variable": "WPFINWGT", "N": 4, "N Miss": 0, "Mean": 15.0},
            {"Variable": "TPTOTINC", "N": 3, "N Miss": 1, "Mean": 3.0},
        ]
    ).to_excel(root / stored_paths[PRIMARY_VALIDATION], index=False)
    pd.DataFrame(
        [
            {"Variable": "SPANEL", "N": 3, "N Miss": 0, "Mean": 2025.0},
            {"Variable": "REPWGT0", "N": 3, "N Miss": 0, "Mean": 20.0},
        ]
    ).to_excel(root / stored_paths[REPLICATE_VALIDATION], index=False)

    artifacts = [
        _stored(PRIMARY_DATA, "artifacts/pu2025_csv.zip", [primary_relative]),
        _stored(REPLICATE_WEIGHTS, "artifacts/rw2025_csv.zip", [replicate_relative]),
        _stored(PRIMARY_SCHEMA, stored_paths[PRIMARY_SCHEMA]),
        _stored(REPLICATE_SCHEMA, stored_paths[REPLICATE_SCHEMA]),
        _stored(PRIMARY_VALIDATION, stored_paths[PRIMARY_VALIDATION]),
        _stored(REPLICATE_VALIDATION, stored_paths[REPLICATE_VALIDATION]),
        _stored(CODEBOOK, "artifacts/2025_SIPP_Data_Dictionary.pdf"),
        _stored(RELEASE_NOTES, "artifacts/2025_SIPP_Release_Notes.pdf"),
        _stored(INPUT_EXAMPLE, "artifacts/2025_sipp_python_input_example.py"),
        _stored(USERS_GUIDE, "artifacts/2025_SIPP_Users_Guide.pdf"),
    ]
    for artifact in artifacts:
        path = root / artifact.relative_path
        if not path.exists():
            path.touch()
    release = DiscoveredRelease(
        survey="sipp",
        year=2025,
        landing_page=definition.landing_page,
        artifacts=[],
    )
    return release, artifacts


def _schema_for(frame: pd.DataFrame) -> list[dict[str, str | int]]:
    result: list[dict[str, str | int]] = []
    for index, (name, dtype) in enumerate(frame.dtypes.items(), start=1):
        column_name = str(name)
        if name == "SSUID":
            schema_type = "string"
        elif pd.api.types.is_integer_dtype(dtype):
            schema_type = "integer"
        else:
            schema_type = "float"
        result.append(
            {
                "varnum": index,
                "name": column_name,
                "label": column_name,
                "dtype": schema_type,
            }
        )
    return result


def _stored(
    role: str,
    relative_path: str,
    extracted_files: list[str] | None = None,
) -> StoredArtifact:
    filename = Path(relative_path).name
    return StoredArtifact(
        role=role,
        source_url=_HTTP_URL.validate_python(f"https://www2.census.gov/{filename}"),
        filename=filename,
        relative_path=relative_path,
        sha256="a" * 64,
        bytes=1,
        extracted_files=extracted_files or [],
    )
