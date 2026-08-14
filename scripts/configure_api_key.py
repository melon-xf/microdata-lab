from __future__ import annotations

import argparse
import getpass
import os
from collections.abc import Sequence
from pathlib import Path

from microdata_lab.secrets import _default_env_path, update_env_file

_SOURCE_KEYS = {
    "census": "CENSUS_API_KEY",
    "fred": "FRED_API_KEY",
}


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Store one source API key without printing it or putting it in shell history."
    )
    parser.add_argument("source", choices=sorted(_SOURCE_KEYS))
    args = parser.parse_args(argv)

    env_path = Path(os.environ.get("MICRODATA_ENV_FILE") or _default_env_path())
    credential = _SOURCE_KEYS[args.source]
    key = getpass.getpass(f"{args.source.upper()} API key (input hidden): ").strip()
    update_env_file(env_path, credential, key)
    print(f"Configured {credential} in {env_path} with protected permissions.")
    print("The key value was not printed.")


if __name__ == "__main__":
    main()
