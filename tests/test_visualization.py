from __future__ import annotations

import json
from pathlib import Path

import pytest

from microdata_lab.visualization import ChartConfig, load_chart_inputs


def test_chart_contract_accepts_complete_bar(tmp_path: Path) -> None:
    data = tmp_path / "data.csv"
    config = tmp_path / "chart.json"
    data.write_text("group,value\nA,1\nB,2\n")
    config.write_text(
        json.dumps(
            {
                "chart_type": "bar",
                "title": "A meaningful title",
                "subtitle": "The subtitle states the measure and year.",
                "source": "Official source",
                "note": "Weighted estimates.",
                "x": "group",
                "y": "value",
                "value_format": "number",
            }
        )
    )

    loaded, rows = load_chart_inputs(data, config)

    assert isinstance(loaded, ChartConfig)
    assert len(rows) == 2


def test_chart_contract_rejects_missing_column(tmp_path: Path) -> None:
    data = tmp_path / "data.csv"
    config = tmp_path / "chart.json"
    data.write_text("group,other\nA,1\n")
    config.write_text(
        json.dumps(
            {
                "chart_type": "bar",
                "title": "Title",
                "subtitle": "Subtitle",
                "source": "Source",
                "x": "group",
                "y": "value",
            }
        )
    )

    with pytest.raises(ValueError, match="value"):
        load_chart_inputs(data, config)
