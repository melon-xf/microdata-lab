"""Rebuild the Hormuz energy-to-inflation watch from the current validated release."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from microdata_lab.adapters.energy_watch import (
    EXPECTED_HORMUZ_FLOW_2024,
    read_hormuz_flow_2024,
)

ANALYSIS_DIR = Path(__file__).resolve().parent
DATA_ROOT = Path(
    os.environ.get("MICRODATA_ROOT") or (Path.home() / ".local" / "share" / "microdata-lab")
)
EVENT_DATE = pd.Timestamp("2026-02-27")
EIA_BYPASS_CAPACITY_MBD = 2.6
SERIES = {
    "DCOILBRENTEU": "Brent crude",
    "GASREGW": "Regular gasoline",
    "T5YIE": "5-year inflation expectations",
}
EXPECTED_BASELINES = {
    "DCOILBRENTEU": 71.32,
    "GASREGW": 2.937,
    "T5YIE": 2.40,
}


def _current_release() -> tuple[dict[str, Any], Path, Path]:
    pointer = json.loads((DATA_ROOT / "current" / "energy_watch.json").read_text())
    release_path = Path(str(pointer["release_path"]))
    manifest = json.loads((release_path / "manifest.json").read_text())
    normalized = next(
        item for item in manifest["normalized_assets"] if item["name"] == "energy_watch"
    )
    return manifest, release_path, release_path / normalized["relative_path"]


def main() -> None:
    manifest, release_path, parquet_path = _current_release()
    raw = pd.read_parquet(parquet_path)
    raw["date"] = pd.to_datetime(raw["date"])
    outputs: list[pd.DataFrame] = []
    summary: dict[str, dict[str, object]] = {}
    benchmark_checks: dict[str, bool] = {}
    hormuz_artifact = next(item for item in manifest["artifacts"] if item["role"] == "hormuz_xlsx")
    hormuz_flow_2024 = read_hormuz_flow_2024(release_path / str(hormuz_artifact["relative_path"]))
    benchmark_checks["EIA_HORMUZ_TOTAL_OIL"] = (
        abs(hormuz_flow_2024 - EXPECTED_HORMUZ_FLOW_2024) < 1e-9
    )

    for series_id, label in SERIES.items():
        frame = raw.loc[raw["series_id"] == series_id].sort_values("date").copy()
        if frame.empty:
            raise ValueError(f"No observations for {series_id}")
        baseline = frame.loc[frame["date"] <= EVENT_DATE].iloc[-1]
        latest = frame.iloc[-1]
        baseline_value = float(baseline["value"])
        latest_value = float(latest["value"])
        frame["series"] = label
        frame["days_since_event"] = (frame["date"] - EVENT_DATE).dt.days
        frame["index"] = frame["value"] / baseline_value * 100
        outputs.append(
            frame[
                [
                    "days_since_event",
                    "date",
                    "series",
                    "series_id",
                    "index",
                    "value",
                    "unit",
                ]
            ]
        )
        expected = EXPECTED_BASELINES[series_id]
        benchmark_checks[series_id] = abs(baseline_value - expected) < 0.0005
        summary[series_id] = {
            "label": label,
            "baseline_date": str(pd.Timestamp(baseline["date"]).date()),
            "baseline_value": baseline_value,
            "latest_date": str(pd.Timestamp(latest["date"]).date()),
            "latest_value": latest_value,
            "percent_change": (latest_value / baseline_value - 1) * 100,
            "absolute_change": latest_value - baseline_value,
        }

    output = pd.concat(outputs, ignore_index=True).sort_values(["days_since_event", "series"])
    output.to_csv(ANALYSIS_DIR / "data.csv", index=False, float_format="%.6f")

    chart = {
        "chart_type": "line",
        "theme": "editorial",
        "title": "Oil and gasoline jumped. Inflation expectations did not.",
        "subtitle": (
            "Brent crude, U.S. regular gasoline, and 5-year breakeven inflation; "
            "last observation on or before Feb. 27, 2026 = 100"
        ),
        "source": "U.S. EIA series retrieved through FRED; Federal Reserve Bank of St. Louis",
        "note": (
            "Shipping disruption was reported March 1, 2026. Series retain their native "
            "daily or weekly frequency. Breakevens are market measures, not household "
            "forecasts. Indexed movements are descriptive; they do not identify pass-through."
        ),
        "x": "days_since_event",
        "y": "index",
        "series": "series",
        "series_order": list(SERIES.values()),
        "x_label": "Days since Feb. 27, 2026",
        "y_label": "Index (baseline = 100)",
        "x_ticks": [0, 30, 60, 90, 120, 150],
        "y_min": 85,
        "y_max": 210,
        "value_format": "number",
        "color_map": {
            "Brent crude": "#D64B5E",
            "Regular gasoline": "#E5A836",
            "5-year inflation expectations": "#087F7A",
        },
        "width": 1600,
        "height": 980,
    }
    (ANALYSIS_DIR / "chart.yaml").write_text(
        yaml.safe_dump(chart, sort_keys=False, allow_unicode=True)
    )

    diagnostics = {
        "analysis": ANALYSIS_DIR.name,
        "source_release_ids": [manifest["release_id"]],
        "row_counts": {
            "normalized_observations": len(raw),
            "output_rows": len(output),
            "series": len(SERIES),
        },
        "weighted_population": {"not_applicable": True},
        "missingness": {
            "output_missing_values": int(output[["date", "index", "value"]].isna().sum().sum())
        },
        "design": {
            "record_unit": "market observation",
            "event_baseline": "last published observation on or before 2026-02-27",
            "frequencies": {"DCOILBRENTEU": "daily", "GASREGW": "weekly", "T5YIE": "daily"},
            "hormuz_exposure_mbd_2024": hormuz_flow_2024,
            "estimated_spare_bypass_mbd": EIA_BYPASS_CAPACITY_MBD,
        },
        "uncertainty": {
            "note": (
                "Published market and sampled retail-price series. No sampling interval is "
                "reported for Brent or breakevens; EIA gasoline is a weighted sample of retail outlets."
            )
        },
        "benchmark": {
            "name": "Pinned pre-disruption observations",
            "observed": summary["DCOILBRENTEU"]["baseline_value"],
            "expected": EXPECTED_BASELINES["DCOILBRENTEU"],
            "passed": all(benchmark_checks.values()),
            "series_checks": benchmark_checks,
        },
        "latest": summary,
    }
    (ANALYSIS_DIR / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
