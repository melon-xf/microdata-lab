from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from platformdirs import user_data_path
from pydantic import AnyHttpUrl, BaseModel, Field

from microdata_lab.secrets import read_runtime_value


class SourceConfig(BaseModel):
    slug: str
    name: str
    agency: str
    access: Literal["public", "licensed_api", "terms_to_verify"]
    landing_page: AnyHttpUrl | None = None
    adapter: str | None = None
    credential: str | None = None
    implemented: bool = False
    enabled: bool = True
    record_unit: str | None = None
    update_cadence: str | None = None
    required_roles: list[str] = Field(default_factory=list)


def resolve_data_root(explicit: Path | None = None) -> Path:
    """Resolve the data root without creating it."""
    if explicit is not None:
        return explicit.expanduser().resolve()
    configured = read_runtime_value("MICRODATA_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return user_data_path("microdata-lab", appauthor=False).resolve()


def initialize_data_root(root: Path) -> None:
    for name in (
        "incoming",
        "quarantine",
        "releases",
        "derived",
        "current",
        "catalog",
        "locks",
        "logs",
    ):
        (root / name).mkdir(parents=True, exist_ok=True)


def load_source_registry() -> dict[str, SourceConfig]:
    registry_path = Path(__file__).resolve().parents[2] / "config" / "sources.yaml"
    payload = yaml.safe_load(registry_path.read_text())
    return {
        slug: SourceConfig.model_validate({"slug": slug, **source})
        for slug, source in payload["sources"].items()
    }
