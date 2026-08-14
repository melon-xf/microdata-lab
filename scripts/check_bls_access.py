from __future__ import annotations

from microdata_lab.bls import build_bls_client, require_bls_response

_PAGE_URL = "https://www.bls.gov/cex/pumd_data.htm"
_ARCHIVE_URL = "https://www.bls.gov/cex/pumd/data/comma/intrvw21.zip"


def main() -> None:
    with build_bls_client() as client:
        page = require_bls_response(client.get(_PAGE_URL))
        normalized_page = page.text.lower()
        page_ok = (
            len(page.content) > 100_000
            and "access denied" not in normalized_page
            and (
                "public-use microdata" in normalized_page
                or "public use microdata" in normalized_page
            )
        )
        print(
            f"BLS page: status={page.status_code} bytes={len(page.content)} "
            f"expected_content={page_ok}"
        )
        if not page_ok:
            raise SystemExit(1)

        with client.stream("GET", _ARCHIVE_URL) as archive:
            require_bls_response(archive)
            prefix = next(archive.iter_bytes(chunk_size=4), b"")[:4]
            archive_ok = prefix.startswith(b"PK")
            print(
                f"BLS archive: status={archive.status_code} "
                f"content_length={archive.headers.get('content-length')} "
                f"zip_magic={archive_ok}"
            )
            if not archive_ok:
                raise SystemExit(1)


if __name__ == "__main__":
    main()
