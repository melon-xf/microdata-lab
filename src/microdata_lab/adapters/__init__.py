"""Official source adapter registry."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from microdata_lab.adapters.ahs import AHSAdapter
from microdata_lab.adapters.base import SourceAdapter
from microdata_lab.adapters.bls_cpi import BlsAdapter
from microdata_lab.adapters.ce import CEAdapter
from microdata_lab.adapters.census import CensusAdapter
from microdata_lab.adapters.eia_861 import EIA861Adapter
from microdata_lab.adapters.energy_watch import EnergyWatchAdapter
from microdata_lab.adapters.eurostat import EurostatAdapter
from microdata_lab.adapters.fred import FredAdapter
from microdata_lab.adapters.gss import GSSAdapter
from microdata_lab.adapters.ilo import IloAdapter
from microdata_lab.adapters.ipums import IPUMSAdapter
from microdata_lab.adapters.meps import MEPSAdapter
from microdata_lab.adapters.oecd import OECDAdapter
from microdata_lab.adapters.oecd_tax_wages import OECDTaxWagesAdapter
from microdata_lab.adapters.scf import SCFAdapter
from microdata_lab.adapters.shed import SHEDAdapter
from microdata_lab.adapters.sipp import SIPPAdapter
from microdata_lab.adapters.who import WhoAdapter
from microdata_lab.adapters.worldbank import WorldBankAdapter
from microdata_lab.config import SourceConfig, load_source_registry

AdapterFactory = Callable[[], SourceAdapter]

_ADAPTERS: dict[str, AdapterFactory] = {
    "ahs": AHSAdapter,
    "bls_cpi": BlsAdapter,
    "scf": SCFAdapter,
    "census": CensusAdapter,
    "eia_861": EIA861Adapter,
    "energy_watch": EnergyWatchAdapter,
    "fred": FredAdapter,
    "acs_pums": lambda: IPUMSAdapter("acs_pums"),
    "cps_asec": lambda: IPUMSAdapter("cps_asec"),
    "atus": lambda: IPUMSAdapter("atus"),
    "shed": SHEDAdapter,
    "sipp": SIPPAdapter,
    "ce": CEAdapter,
    "oecd": OECDAdapter,
    "oecd_tax_wages": lambda: OECDTaxWagesAdapter(
        definition_path=Path(__file__).resolve().parents[3] / "config/oecd-tax-wages/tax-wedge.yaml"
    ),
    "oecd_sha": lambda: OECDTaxWagesAdapter(
        definition_path=Path(__file__).resolve().parents[3] / "config/oecd-sha/sha.yaml"
    ),
    "worldbank": WorldBankAdapter,
    "meps": MEPSAdapter,
    "eurostat": EurostatAdapter,
    "gss": GSSAdapter,
    "ilo": IloAdapter,
    "who": WhoAdapter,
}


def get_source_config(slug: str) -> SourceConfig:
    registry = load_source_registry()
    try:
        return registry[slug]
    except KeyError as error:
        raise ValueError(f"Unknown source: {slug}") from error


def get_adapter(slug: str) -> SourceAdapter:
    source = get_source_config(slug)
    if not source.implemented:
        raise NotImplementedError(f"Source adapter is not implemented: {slug}")
    adapter_name = source.adapter or slug
    try:
        return _ADAPTERS[adapter_name]()
    except KeyError as error:
        raise ValueError(f"No adapter factory is registered for {adapter_name}") from error


def enabled_source_slugs() -> list[str]:
    return sorted(
        slug
        for slug, source in load_source_registry().items()
        if source.implemented and source.enabled
    )
