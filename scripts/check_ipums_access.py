from __future__ import annotations

import httpx

from microdata_lab.secrets import require_secret

_COLLECTIONS = {
    "ACS PUMS": "usa",
    "CPS ASEC": "cps",
    "ATUS": "atus",
}


def main() -> None:
    key = require_secret("IPUMS_API_KEY")
    all_ready = True
    with httpx.Client(
        base_url="https://api.ipums.org",
        headers={
            "Authorization": key,
            "Accept": "application/json",
            "User-Agent": "microdata-lab/0.1",
        },
        follow_redirects=True,
        timeout=60,
    ) as client:
        for name, collection in _COLLECTIONS.items():
            response = client.get(
                "/extracts",
                params={
                    "collection": collection,
                    "version": 2,
                    "pageNumber": 1,
                    "pageSize": 1,
                },
            )
            ready = response.status_code == 200
            all_ready &= ready
            print(f"{name}: status={response.status_code} registered={ready}")

    raise SystemExit(0 if all_ready else 1)


if __name__ == "__main__":
    main()
