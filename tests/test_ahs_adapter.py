from __future__ import annotations

import json
from pathlib import Path

import httpx
import pandas as pd
import pyarrow.parquet as pq
from pydantic import AnyHttpUrl, TypeAdapter

from microdata_lab.adapters.ahs import (
    CODEBOOK_DETAILS,
    CODEBOOK_VARIABLES,
    CODEBOOK_YEARS,
    DESIGN_REPORT,
    GETTING_STARTED,
    NATIONAL_CSV,
    VALUE_LABELS,
    VARIANCE_GUIDE,
    VERIFICATION_WORKBOOK,
    VERSION_CONTROL,
    AHSAdapter,
    AHSBenchmark,
    AHSCodebookContract,
    AHSReleaseDefinition,
    AHSStaticArtifact,
    AHSTableContract,
    AHSWeightContract,
)
from microdata_lab.models import StoredArtifact

_url_adapter = TypeAdapter(AnyHttpUrl)
LANDING = (
    "https://www.census.gov/programs-surveys/ahs/data/2023/ahs-2023-national-public-use-file.html"
)
PAGE_ROLES = {
    NATIONAL_CSV,
    VERSION_CONTROL,
    VERIFICATION_WORKBOOK,
    VALUE_LABELS,
}
STATIC_ROLES = {
    DESIGN_REPORT,
    VARIANCE_GUIDE,
    CODEBOOK_VARIABLES,
    CODEBOOK_DETAILS,
    CODEBOOK_YEARS,
    GETTING_STARTED,
}


def _definition() -> AHSReleaseDefinition:
    static = [
        AHSStaticArtifact(
            role=role,
            url=_url_adapter.validate_python(f"https://example.test/{role}.json"),
            filename=f"{role}.json",
            documentation=role in {DESIGN_REPORT, VARIANCE_GUIDE},
        )
        for role in sorted(STATIC_ROLES)
    ]
    return AHSReleaseDefinition(
        year=2023,
        revision="1.1",
        landing_page=_url_adapter.validate_python(LANDING),
        required_artifacts=sorted(PAGE_ROLES | STATIC_ROLES),
        static_artifacts=static,
        tables={
            "household": AHSTableContract(
                filename="household.csv",
                rows=3,
                columns=7,
                key=["CONTROL"],
            ),
            "mortgage": AHSTableContract(
                filename="mortgage.csv",
                rows=2,
                columns=3,
                key=["CONTROL", "MORTLINE"],
            ),
            "person": AHSTableContract(
                filename="person.csv",
                rows=3,
                columns=3,
                key=["CONTROL", "PERSONID"],
            ),
            "project": AHSTableContract(
                filename="project.csv",
                rows=3,
                columns=2,
                key=[],
            ),
        },
        weight_contract=AHSWeightContract(
            full_sample="WEIGHT",
            split_sample=["SP1WEIGHT", "SP2WEIGHT"],
            replicate_prefix="REPWEIGHT",
            replicate_count=2,
            variance_factor=1.0,
        ),
        benchmark=AHSBenchmark(
            table="household",
            universe_variable="INTSTATUS",
            universe_values=["1"],
            expected_status_values=["1", "2"],
            expected_estimate_thousands=3,
            expected_moe90_thousands=0,
            estimate_rounding_tolerance=0.5,
        ),
        codebook_contract=AHSCodebookContract(
            minimum_variables=3,
            minimum_details=3,
            required_year_option="2023 National",
            required_variables=["CONTROL", "INTSTATUS", "WEIGHT"],
        ),
    )


def _page() -> str:
    return "".join(
        [
            '<a href="https://www2.census.gov/AHS%202023%20National%20PUF%20v1.1%20CSV.zip">data</a>',
            '<a href="https://www2.census.gov/AHS%202023%20National%20PUF%20Version%20Control.pdf">version</a>',
            (
                '<a href="//www2.census.gov/AHS%202023%20Table%20Specifications%20'
                'and%20PUF%20Estimates%20for%20User%20Verification.xlsx">verify</a>'
            ),
            '<a href="//www2.census.gov/AHS%202023%20Value%20Labels%20Package.zip">labels</a>',
        ]
    )


def _release(adapter: AHSAdapter):
    return adapter.discover(2023)


def _stored(
    role: str,
    relative_path: str,
    *,
    extracted_files: list[str] | None = None,
) -> StoredArtifact:
    return StoredArtifact(
        role=role,
        source_url=_url_adapter.validate_python(f"https://example.test/{role}"),
        filename=Path(relative_path).name,
        relative_path=relative_path,
        sha256="a" * 64,
        bytes=1,
        extracted_files=extracted_files or [],
        documentation=role in {VERSION_CONTROL, DESIGN_REPORT, VARIANCE_GUIDE},
    )


def _fixture(root: Path, release) -> list[StoredArtifact]:
    tables = {
        "household.csv": pd.DataFrame(
            {
                "CONTROL": ["A", "B", "C"],
                "INTSTATUS": ["'1'", "'1'", "'2'"],
                "WEIGHT": [1000.0, 2000.0, 500.0],
                "SP1WEIGHT": [1000.0, 0.0, 500.0],
                "SP2WEIGHT": [0.0, 2000.0, 500.0],
                "REPWEIGHT1": [900.0, 2100.0, 500.0],
                "REPWEIGHT2": [1100.0, 1900.0, 500.0],
            }
        ),
        "mortgage.csv": pd.DataFrame(
            {
                "CONTROL": ["A", "A"],
                "MORTLINE": [1, 2],
                "AMMORT": [100, 200],
            }
        ),
        "person.csv": pd.DataFrame(
            {
                "CONTROL": ["A", "A", "B"],
                "PERSONID": [1, 2, 1],
                "AGE": [40, 38, 29],
            }
        ),
        "project.csv": pd.DataFrame(
            {
                "CONTROL": ["A", "A", "B"],
                "JOBTYPE": ["'01'", "'01'", "'02'"],
            }
        ),
    }
    extracted_files: list[str] = []
    for filename, frame in tables.items():
        relative = f"extracted/{NATIONAL_CSV}/{filename}"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
        extracted_files.append(relative)

    artifacts: list[StoredArtifact] = []
    for discovered in release.artifacts:
        role = str(getattr(discovered.role, "value", discovered.role))
        relative = f"artifacts/{role}/{discovered.filename}"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if role == VERIFICATION_WORKBOOK:
            with pd.ExcelWriter(path) as writer:
                pd.DataFrame([[None] * 6 for _ in range(5)]).to_excel(
                    writer,
                    sheet_name="General Housing",
                    index=False,
                    header=False,
                )
                pd.DataFrame([["Total", "INTSTATUS = '1'", None, 3, 3, 0]]).to_excel(
                    writer,
                    sheet_name="General Housing",
                    startrow=5,
                    index=False,
                    header=False,
                )
        elif role == CODEBOOK_VARIABLES:
            path.write_text(
                json.dumps(
                    [
                        {"summary": {"name": "CONTROL"}},
                        {"summary": {"name": "INTSTATUS"}},
                        {"summary": {"name": "WEIGHT"}},
                    ]
                )
            )
        elif role == CODEBOOK_DETAILS:
            path.write_text(json.dumps([{}, {}, {}]))
        elif role == CODEBOOK_YEARS:
            path.write_text(json.dumps([{"id": "2023 National"}]))
        else:
            path.write_bytes(b"fixture")
        artifacts.append(
            _stored(
                role,
                relative,
                extracted_files=extracted_files if role == NATIONAL_CSV else None,
            )
        )
    return artifacts


def test_ahs_discovers_exact_official_roles() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=_page()))
    )
    adapter = AHSAdapter(definition=_definition(), client=client)
    release = _release(adapter)
    roles = {str(getattr(item.role, "value", item.role)) for item in release.artifacts}
    assert roles == PAGE_ROLES | STATIC_ROLES
    verification = next(item for item in release.artifacts if item.role == VERIFICATION_WORKBOOK)
    assert not verification.documentation
    getting_started = next(item for item in release.artifacts if item.role == GETTING_STARTED)
    assert not getting_started.documentation
    assert release.source_metadata["variance_factor"] == 1.0
    client.close()


def test_ahs_validates_relational_design_and_normalizes(tmp_path: Path) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=_page()))
    )
    adapter = AHSAdapter(definition=_definition(), client=client)
    release = _release(adapter)
    artifacts = _fixture(tmp_path, release)

    validation = adapter.validate_release(tmp_path, release, artifacts)
    assert validation.passed, {
        name: passed for name, passed in validation.checks.items() if not passed
    }
    assert validation.checks["ahs_project_foreign_keys"]
    assert "ahs_project_keys_unique" not in validation.checks

    outputs = adapter.normalize_release(tmp_path, release, artifacts)
    assert {path.name for path in outputs} == {
        "household.parquet",
        "mortgage.parquet",
        "person.parquet",
        "project.parquet",
    }
    assert pq.ParquetFile(tmp_path / "normalized/household.parquet").metadata.num_rows == 3
    client.close()


def test_ahs_rejects_bad_replicate_uncertainty(tmp_path: Path) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=_page()))
    )
    adapter = AHSAdapter(definition=_definition(), client=client)
    release = _release(adapter)
    artifacts = _fixture(tmp_path, release)
    household = tmp_path / f"extracted/{NATIONAL_CSV}/household.csv"
    frame = pd.read_csv(household)
    frame.loc[0, "REPWEIGHT1"] = 2000.0
    frame.to_csv(household, index=False)

    validation = adapter.validate_release(tmp_path, release, artifacts)
    assert not validation.passed
    assert not validation.checks["ahs_benchmark_moe90"]
    client.close()
