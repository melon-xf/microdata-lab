from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyreadstat

from microdata_lab.scf_validation import validate_scf_files


def test_validates_scf_implicates_and_replicate_design(tmp_path: Path) -> None:
    rows = []
    for family in (1, 2):
        for implicate in range(1, 6):
            rows.append(
                {
                    "YY1": family,
                    "Y1": family * 10 + implicate,
                    "WGT": 100.0,
                    "NETWORTH": family * 1000 + implicate,
                    "CCBAL": family * 10,
                }
            )
    summary = tmp_path / "summary.csv"
    pd.DataFrame(rows).to_csv(summary, index=False)

    replicate_columns = {
        "y1": [11, 21],
        "yy1": [1, 2],
        **{f"wt1b{index}": [100.0, 100.0] for index in range(1, 1000)},
        **{f"mm{index}": [1.0, 1.0] for index in range(1, 1000)},
    }
    replicate = pd.DataFrame(replicate_columns)
    replicate_path = tmp_path / "weights.dta"
    pyreadstat.write_dta(replicate, replicate_path)

    full_path = tmp_path / "full.dta"
    pyreadstat.write_dta(pd.DataFrame({"y1": [row["Y1"] for row in rows]}), full_path)

    checks, notes = validate_scf_files(summary, replicate_path, full_path)

    assert all(checks.values()), notes
    assert not notes
