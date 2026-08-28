"""Parser and adapter tests for the BLS multi-series adapter.

All fixtures are tiny embedded TSV snippets copied from the verified real
layouts (padding, CRLF endings); no test touches the network.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pandas as pd
import pytest

from microdata_lab.adapters.bls_series import (
    AVERAGE_PERIODS,
    DATA_FILES,
    METADATA_FILES,
    BlsSeriesAccessError,
    BlsSeriesAdapter,
    data_role,
    decompose_series_id,
    looks_like_block_page,
    parse_areas,
    parse_catalog_series,
    parse_items,
    parse_observations,
    parse_periods,
    resolve_period_date,
)
from microdata_lab.models import DiscoveredRelease, StoredArtifact

# Real layout: series_id padded with trailing spaces, tab-separated.
CU_SERIES = (
    "series_id        \tarea_code\titem_code\tseasonal\tperiodicity_code\tbase_code"
    "\tbase_period\tseries_title\tfootnote_codes\tbegin_year\tbegin_period\tend_year\tend_period\n"
    "CUUR0000SA0      \t0000\tSA0\tU\tR\tS\t1982-84=100\t"
    "All items in U.S. city average, all urban consumers, not seasonally adjusted"
    "\t\t1913\tM01\t2026\tM07\n"
    "CUURS49ASEFV     \tS49A\tSEFV\tU\tR\tS\t1982-84=100\t"
    "Food away from home in Los Angeles-Long Beach-Anaheim, CA, all urban "
    "consumers, not seasonally adjusted\t\t1952\tM12\t2026\tM07\n"
)

CU_AREA = (
    "area_code\tarea_name\tdisplay_level\tselectable\tsort_sequence\n"
    "0000\tU.S. city average\t0\tT\t1\n"
    "S49A\tLos Angeles-Long Beach-Anaheim, CA\t4\tT\t425\n"
)

CU_ITEM = (
    "item_code\titem_name\tdisplay_level\tselectable\tsort_sequence\n"
    "SA0\tAll items\t0\tT\t1\n"
    "SEFV\tFood away from home\t2\tT\t39\n"

)

# Real layout: CRLF line endings, no padding, 16 period rows.
CU_PERIOD = (
    "period\tperiod_abbr\tperiod_name\r\n"
    "M01\tJAN\tJanuary\r\n"
    "M12\tDEC\tDecember\r\n"
    "M13\tAN AV\tAnnual Average\r\n"
    "S01\tHALF1\tFirst Half\r\n"
    "S02\tHALF2\tSecond Half\r\n"
    "S03\tAN AV\tAnnual Average\r\n"
)

# Real layout: padded series_id and value columns, CRLF endings.
CU_DATA = (
    "series_id        \tyear\tperiod\t       value\tfootnote_codes\r\n"
    "CUURS49ASEFV     \t1952\tM12\t        20.8\t\r\n"
    "CUURS49ASEFV     \t1953\tM01\t        20.9\t\r\n"
    "CUURS49ASEFV     \t1953\tM13\t        21.0\t\r\n"
    "CUUR0000SA0      \t2026\tM06\t       322.561\t\r\n"
)

# Real WAF denial: 403, text/html, ~29 lines, starts with a doctype.
BLOCK_PAGE = (
    "<!DOCTYPE HTML>\n<html lang=\"en-us\">\n<head>\n<title>Access Denied</title>\n"
    "</head>\n<body>\n<p>You don't have permission to access this resource.</p>\n"
    "</body>\n</html>\n"
)


def test_parse_catalog_series_strips_padding() -> None:
    df = parse_catalog_series(CU_SERIES)
    assert list(df.columns)[:4] == ["series_id", "area_code", "item_code", "seasonal"]
    row = df[df["series_id"] == "CUURS49ASEFV"].iloc[0]
    assert row["area_code"] == "S49A"
    assert row["item_code"] == "SEFV"
    assert row["seasonal"] == "U"
    assert row["begin_year"] == 1952
    assert row["begin_period"] == "M12"
    assert "Los Angeles" in row["series_title"]


def test_parse_areas_items_periods() -> None:
    areas = parse_areas(CU_AREA)
    assert areas.set_index("area_code").loc["S49A", "area_name"].startswith("Los Angeles")
    items = parse_items(CU_ITEM)
    assert items.set_index("item_code").loc["SEFV", "item_name"] == "Food away from home"
    periods = parse_periods(CU_PERIOD)
    assert set(periods["period"]) == {"M01", "M12", "M13", "S01", "S02", "S03"}
    assert periods.set_index("period").loc["S03", "period_name"] == "Annual Average"


def test_parse_observations_handles_padding_crlf_and_filtering() -> None:
    df = parse_observations(CU_DATA)
    assert len(df) == 4
    first = df.iloc[0]
    assert first["series_id"] == "CUURS49ASEFV"
    assert first["year"] == 1952
    assert first["value"] == 20.8
    assert first["footnote_codes"] == ""

    filtered = parse_observations(CU_DATA, wanted={"CUURS49ASEFV"})
    assert set(filtered["series_id"]) == {"CUURS49ASEFV"}
    assert len(filtered) == 3


def test_resolve_period_date_semantics() -> None:
    assert resolve_period_date(1952, "M12") == "1952-12-01"
    assert resolve_period_date(2026, "M01") == "2026-01-01"
    for average in AVERAGE_PERIODS:
        assert resolve_period_date(1953, average) is None
    assert resolve_period_date(1953, "bogus") is None


def test_looks_like_block_page() -> None:
    assert looks_like_block_page(BLOCK_PAGE.encode())
    assert looks_like_block_page(b"\n  <html><body>denied</body></html>")
    assert not looks_like_block_page(CU_DATA.encode())
    assert not looks_like_block_page(CU_PERIOD.encode())


def test_decompose_series_id() -> None:
    parts = decompose_series_id("CUURS49ESEFV")
    assert parts == {
        "survey_prefix": "CU",
        "seasonal": "U",
        "periodicity": "R",
        "area_item": "S49ESEFV",
    }
    with pytest.raises(ValueError, match="Not a CPI-U series id"):
        decompose_series_id("GNPCA")


def _store(
    run_root: Path, role: str, filename: str, content: str, size: int | None = None
) -> StoredArtifact:
    rel = f"artifacts/{role}/{filename}"
    path = run_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return StoredArtifact(
        role=role,
        source_url=f"https://download.bls.gov/pub/time.series/cu/{filename}",
        filename=filename,
        relative_path=rel,
        sha256="0" * 64,
        bytes=size if size is not None else len(content.encode()),
    )


def _release() -> DiscoveredRelease:
    return BlsSeriesAdapter().discover(year=2026)


def test_discover_lists_complete_official_release() -> None:
    release = _release()
    roles = [str(a.role) for a in release.artifacts]
    assert len(roles) == len(set(roles)), "artifact roles must be unique"
    assert set(METADATA_FILES.values()) <= set(roles)
    assert {data_role(name) for name in DATA_FILES} <= set(roles)
    assert release.source_metadata["identifying_user_agent"] is True


def test_validate_release_fails_loudly_on_block_page(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    artifacts = [
        _store(run_root, "catalog_series", "cu.series", CU_SERIES),
        _store(run_root, "catalog_area", "cu.area", CU_AREA),
        _store(run_root, "catalog_item", "cu.item", CU_ITEM),
        _store(run_root, "catalog_period", "cu.period", CU_PERIOD),
        _store(
            run_root,
            data_role("cu.data.10.OtherWest"),
            "cu.data.10.OtherWest",
            BLOCK_PAGE,
            size=1325,
        ),
    ]
    adapter = BlsSeriesAdapter()
    result = adapter.validate_release(run_root, _release(), artifacts)
    assert not result.passed
    assert result.checks[f"not_block_page_{data_role('cu.data.10.OtherWest')}"] is False
    assert any("BLS_USER_AGENT" in note for note in result.notes)


def test_validate_release_benchmark_passes_with_real_layout(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    artifacts = [
        _store(run_root, "catalog_series", "cu.series", CU_SERIES),
        _store(run_root, "catalog_area", "cu.area", CU_AREA),
        _store(run_root, "catalog_item", "cu.item", CU_ITEM),
        _store(run_root, "catalog_period", "cu.period", CU_PERIOD),
        # Stored bytes reflect a real multi-megabyte data file; the fixture
        # content is a tiny excerpt of the verified layout.
        _store(
            run_root,
            data_role("cu.data.10.OtherWest"),
            "cu.data.10.OtherWest",
            CU_DATA,
            size=31_471_279,
        ),
    ]
    adapter = BlsSeriesAdapter()
    result = adapter.validate_release(run_root, _release(), artifacts)
    assert result.checks["benchmark_value"] is True
    assert result.passed, result.notes


def test_normalize_release_writes_tidy_parquet(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    artifacts = [
        _store(run_root, "catalog_series", "cu.series", CU_SERIES),
        _store(run_root, "catalog_area", "cu.area", CU_AREA),
        _store(run_root, "catalog_item", "cu.item", CU_ITEM),
        _store(run_root, "catalog_period", "cu.period", CU_PERIOD),
        _store(run_root, data_role("cu.data.10.OtherWest"), "cu.data.10.OtherWest", CU_DATA),
    ]
    adapter = BlsSeriesAdapter(
        definition=BlsSeriesAdapter().definition.model_copy(
            update={"data_files": ("cu.data.10.OtherWest",)}
        )
    )
    written = adapter.normalize_release(run_root, _release(), artifacts)
    names = {path.name for path in written}
    assert "cu_series.parquet" in names
    assert "cu_observations.parquet" in names
    observations = pd.read_parquet(run_root / "normalized" / "cu_observations.parquet")
    row = observations[observations["series_id"] == "CUURS49ASEFV"].iloc[0]
    assert row["area_name"].startswith("Los Angeles")


_FIXTURES = {
    "cu.series": CU_SERIES,
    "cu.area": CU_AREA,
    "cu.item": CU_ITEM,
    "cu.period": CU_PERIOD,
    "cu.data.10.OtherWest": CU_DATA,
}


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _ok_handler(request: httpx.Request) -> httpx.Response:
    name = request.url.path.rsplit("/", 1)[-1]
    if name in _FIXTURES:
        return httpx.Response(200, text=_FIXTURES[name])
    return httpx.Response(404, text="not found")


def test_fetch_catalog_returns_metadata_frames() -> None:
    adapter = BlsSeriesAdapter(client=_mock_client(_ok_handler))
    catalog = adapter.fetch_catalog()
    assert set(catalog) == {"series", "areas", "items", "periods"}
    assert "CUURS49ASEFV" in set(catalog["series"]["series_id"])


def test_fetch_series_tidy_output_with_geography() -> None:
    adapter = BlsSeriesAdapter(client=_mock_client(_ok_handler))
    df = adapter.fetch_series(["CUURS49ASEFV"], data_files=["cu.data.10.OtherWest"])
    assert list(df.columns) == [
        "series_id",
        "date",
        "period",
        "year",
        "value",
        "area_code",
        "area_name",
    ]
    # M13 annual average excluded by default.
    assert set(df["period"]) == {"M12", "M01"}
    first = df.iloc[0]
    assert first["date"] == "1952-12-01"
    assert first["value"] == 20.8
    assert first["area_code"] == "S49A"
    assert first["area_name"].startswith("Los Angeles")


def test_fetch_series_include_averages_keeps_undated_rows() -> None:
    adapter = BlsSeriesAdapter(client=_mock_client(_ok_handler))
    df = adapter.fetch_series(
        ["CUURS49ASEFV"], data_files=["cu.data.10.OtherWest"], include_averages=True
    )
    annual = df[df["period"] == "M13"].iloc[0]
    assert pd.isna(annual["date"])
    assert annual["value"] == 21.0


def test_fetch_series_filters_resolve_from_catalog() -> None:
    adapter = BlsSeriesAdapter(client=_mock_client(_ok_handler))
    df = adapter.fetch_series(area_codes=["S49A"], data_files=["cu.data.10.OtherWest"])
    assert set(df["series_id"]) == {"CUURS49ASEFV"}


def test_fetch_series_requires_selection() -> None:
    adapter = BlsSeriesAdapter(client=_mock_client(_ok_handler))
    with pytest.raises(ValueError, match="series_ids or at least one catalog filter"):
        adapter.fetch_series()


def test_fetch_series_block_page_fails_loudly() -> None:
    def denied(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text=BLOCK_PAGE)

    adapter = BlsSeriesAdapter(client=_mock_client(denied))
    with pytest.raises(BlsSeriesAccessError, match="BLS_USER_AGENT"):
        adapter.fetch_series(["CUURS49ASEFV"], data_files=["cu.data.10.OtherWest"])
