from __future__ import annotations

import getpass
import os
import re
from pathlib import Path

from microdata_lab.secrets import _default_env_path, update_env_file

_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def main() -> None:
    print("Configure the identifying contact required by the BLS automated-access policy.")
    env_path = Path(os.environ.get("MICRODATA_ENV_FILE") or _default_env_path())
    print(f"The value is stored only in {env_path} with mode 0600 and is sent only to BLS hosts.")
    name = input("Your name: ").strip()
    email = getpass.getpass("Your contact email (hidden): ").strip()
    if not name or any(ord(character) < 32 or ord(character) > 126 for character in name):
        raise SystemExit("Name must contain printable ASCII characters only.")
    if not _EMAIL.fullmatch(email):
        raise SystemExit("Enter a valid single-line email address.")

    user_agent = f"Microdata Lab/0.1 ({name}; {email})"
    update_env_file(env_path, "BLS_USER_AGENT", user_agent)
    print("BLS identifying User-Agent configured without displaying it.")


if __name__ == "__main__":
    main()
