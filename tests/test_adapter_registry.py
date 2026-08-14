from __future__ import annotations

import pytest

from microdata_lab.adapters import enabled_source_slugs, get_adapter
from microdata_lab.adapters.scf import SCFAdapter


def test_registry_returns_implemented_adapter() -> None:
    adapter = get_adapter("scf")
    try:
        assert isinstance(adapter, SCFAdapter)
    finally:
        adapter.close()


def test_enabled_sources_exclude_planned_adapters() -> None:
    assert enabled_source_slugs() == [
        "acs_pums",
        "ahs",
        "atus",
        "bls_cpi",
        "ce",
        "census",
        "cps_asec",
        "eia_861",
        "energy_watch",
        "eurostat",
        "fred",
        "gss",
        "ilo",
        "meps",
        "oecd",
        "oecd_sha",
        "oecd_tax_wages",
        "scf",
        "shed",
        "sipp",
        "who",
        "worldbank",
    ]


def test_registry_fails_visibly_for_unknown_adapter() -> None:
    with pytest.raises(ValueError, match="Unknown source"):
        get_adapter("not-a-survey")
