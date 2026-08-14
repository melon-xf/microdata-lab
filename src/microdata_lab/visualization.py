from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class ChartConfig(BaseModel):
    chart_type: Literal[
        "bar",
        "line",
        "area",
        "dot",
        "dumbbell",
        "ratio_ladder",
        "choropleth",
        "step",
        "slope",
        "arrow",
        "lollipop",
        "strip",
        "facet",
    ]
    orientation: Literal["horizontal", "vertical"] = "vertical"
    theme: Literal["default", "editorial", "bauhaus", "swiss"] = "default"
    eyebrow: str | None = None
    show_value_labels: bool = True
    # pictogram/coins: glyph shape ("circle" | "coin" | "person"); ratio
    # charts: optional reference line value (default 1.0)
    glyph: Literal["circle", "coin", "person"] = "circle"
    reference: float | None = None
    # choropleth: how to join data rows to map features
    region_key: str | None = None  # data column holding state codes/names
    region_format: Literal["name", "stusps", "statfp"] = "stusps"
    title: str = Field(min_length=1)
    subtitle: str = Field(min_length=1)
    source: str = Field(min_length=1)
    note: str = ""
    annotations: list[dict[str, object]] | None = None
    facet: str | None = None
    x: str = Field(min_length=1, default="x")
    y: str = Field(min_length=1)
    series: str | None = None
    ci_low: str | None = None
    ci_high: str | None = None
    value_format: Literal["number", "percent", "currency", "compact_currency"] = "number"
    color: str = "#008C95"
    x_label: str | None = None
    y_label: str | None = None
    # Article-fidelity controls: explicit axis ticks/limits, per-series
    # linetype, legend order, and vertical annotation lines.
    x_ticks: list[float] | None = None
    y_ticks: list[float] | None = None
    y_min: float | None = None
    y_max: float | None = None
    tick_suffix: str = ""
    ratio_label: str | None = None
    ratio_suffix: str = ""
    x_tick_suffix: str | None = None
    series_order: list[str] | None = None
    line_style: dict[str, Literal["solid", "dashed", "dotted"]] | None = None
    vline: list[dict[str, float | str]] | None = None
    color_map: dict[str, str] | None = None
    width: int = Field(default=1400, ge=640, le=4000)
    height: int = Field(default=900, ge=400, le=3000)


def load_chart_inputs(
    data_path: Path, config_path: Path
) -> tuple[ChartConfig, list[dict[str, str]]]:
    if config_path.suffix.lower() in {".yaml", ".yml"}:
        config_payload = yaml.safe_load(config_path.read_text())
    else:
        config_payload = json.loads(config_path.read_text())
    config = ChartConfig.model_validate(config_payload)
    with data_path.open(newline="") as source:
        reader = csv.DictReader(source)
        rows = list(reader)
        fields = set(reader.fieldnames or [])
    if not rows:
        raise ValueError(f"Chart data is empty: {data_path}")
    if (config.ci_low is None) != (config.ci_high is None):
        raise ValueError("ci_low and ci_high must be configured together")
    required = {config.x, config.y}
    if config.chart_type == "choropleth":
        required = {config.region_key or config.x, config.y}
    if config.ci_low and config.ci_high:
        required.update({config.ci_low, config.ci_high})
    missing = required - fields
    if missing:
        raise ValueError(f"Chart data is missing columns: {', '.join(sorted(missing))}")
    for row_number, row in enumerate(rows, start=2):
        try:
            float(row[config.y])
            if config.ci_low and config.ci_high:
                float(row[config.ci_low])
                float(row[config.ci_high])
        except (TypeError, ValueError) as error:
            raise ValueError(f"Non-numeric {config.y} value on CSV row {row_number}") from error
    return config, rows


def render_static(data_path: Path, config_path: Path, output_path: Path) -> None:
    config, _ = load_chart_inputs(data_path, config_path)
    root = _project_root()
    configured = os.environ.get("MICRODATA_RSCRIPT")
    candidates = [Path(configured)] if configured else []
    candidates.extend([root / ".r-env/bin/Rscript"])
    system = shutil.which("Rscript")
    if system:
        candidates.append(Path(system))
    rscript = next((candidate for candidate in candidates if candidate.is_file()), None)
    if rscript is None:
        raise RuntimeError("Rscript is unavailable; run scripts/bootstrap_r.sh")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with _renderer_config(config_path, config) as renderer_config:
        subprocess.run(
            [
                str(rscript),
                str(root / "viz/static/render_static.R"),
                str(data_path.resolve()),
                str(renderer_config),
                str(output_path.resolve()),
            ],
            check=True,
        )


def render_interactive(data_path: Path, config_path: Path, output_path: Path) -> None:
    config, _ = load_chart_inputs(data_path, config_path)
    root = _project_root()
    npm = shutil.which("npm")
    if npm is None:
        raise RuntimeError("npm is unavailable; install Node.js 22 or newer")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with _renderer_config(config_path, config) as renderer_config:
        subprocess.run(
            [
                npm,
                "--prefix",
                str(root / "viz/interactive"),
                "run",
                "render",
                "--",
                "--input",
                str(data_path.resolve()),
                "--config",
                str(renderer_config),
                "--output",
                str(output_path.resolve()),
            ],
            check=True,
        )


def write_chart_config(config: ChartConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = config.model_dump(mode="json")
    if path.suffix.lower() in {".yaml", ".yml"}:
        path.write_text(yaml.safe_dump(payload, sort_keys=False))
    else:
        path.write_text(json.dumps(payload, indent=2) + "\n")


@contextmanager
def _renderer_config(config_path: Path, config: ChartConfig) -> Iterator[Path]:
    if config_path.suffix.lower() == ".json":
        yield config_path.resolve()
        return
    with tempfile.TemporaryDirectory(prefix="microdata-chart-") as directory:
        json_path = Path(directory) / "chart.json"
        json_path.write_text(json.dumps(config.model_dump(mode="json"), indent=2) + "\n")
        yield json_path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]
