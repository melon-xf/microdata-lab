from __future__ import annotations

from microdata_lab.models import ArtifactRole


def test_required_scf_roles_are_explicit() -> None:
    assert {role.value for role in ArtifactRole} == {
        "full_data_stata",
        "replicate_weights_stata",
        "summary_extract_csv",
        "summary_extract_stata",
        "codebook",
        "standard_error_documentation",
        "changes",
        "variable_definitions",
    }
