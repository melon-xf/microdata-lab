from __future__ import annotations

import os
from pathlib import Path

from microdata_lab.adapters import enabled_source_slugs, get_adapter
from microdata_lab.catalog import rebuild_catalog
from microdata_lab.config import initialize_data_root, resolve_data_root
from microdata_lab.storage import sync_release


def main() -> None:
    root = resolve_data_root(
        Path(os.environ["MICRODATA_ROOT"]) if os.environ.get("MICRODATA_ROOT") else None
    )
    initialize_data_root(root)
    promoted: list[str] = []
    failures: list[str] = []
    for slug in enabled_source_slugs():
        try:
            with get_adapter(slug) as adapter:
                discovered = adapter.discover()
                result = sync_release(
                    discovered,
                    root,
                    adapter=adapter,
                    client=adapter.download_client(),
                )
            if result.changed:
                promoted.append(result.manifest.release_id)
        except Exception as error:
            failures.append(f"{slug}: {error}")

    if promoted:
        counts = rebuild_catalog(root)
        print(
            f"Promoted {', '.join(promoted)}; "
            f"catalog now has {counts.releases} release(s), "
            f"{counts.variables} variables, and {counts.documents} documents."
        )
    if failures:
        raise RuntimeError("Scheduled source failures: " + "; ".join(failures))


if __name__ == "__main__":
    main()
