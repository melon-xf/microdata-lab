from __future__ import annotations

import getpass
import os
from pathlib import Path

from microdata_lab.secrets import _default_env_path, update_env_file


def main() -> None:
    env_path = Path(os.environ.get("MICRODATA_ENV_FILE") or _default_env_path())
    key = getpass.getpass("IPUMS API key (input hidden): ").strip()
    update_env_file(env_path, "IPUMS_API_KEY", key)
    print(f"Configured IPUMS_API_KEY in {env_path} with protected permissions.")
    print("The key value was not printed.")


if __name__ == "__main__":
    main()
