"""Ingest validation, the derived delay cause, and the query runner's local backend."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pyarrow as pa
import pytest

from delaystats import athena, ingest


def _zip(path: Path, header: list[str], rows: list[list[str]]) -> Path:
    text = "\n".join(",".join(f'"{v}"' for v in line) for line in [header, *rows]) + "\n"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("On_Time_2023_1.csv", text)
        archive.writestr("readme.html", "<html/>")
    return path


def _row(**overrides: str) -> list[str]:
    values = {name: "" for name in ingest.COLUMNS}
    values |= {
        "Year": "2023",
        "Month": "1",
        "DayofMonth": "2",
        "DayOfWeek": "1",
        "FlightDate": "2023-01-02",
        "Reporting_Airline": "AS",
        "Origin": "SEA",
        "Dest": "SFO",
        "ArrDelay": "-3.00",
        "ArrDel15": "0.00",
        "Cancelled": "0.00",
        "Diverted": "0.00",
        "Distance": "679.00",
    }
    values |= overrides
    return list(values.values())


def test_header_missing_columns_named(tmp_path: Path) -> None:
    header = [c for c in ingest.COLUMNS if c not in ("ArrDelay", "NASDelay")]
    path = _zip(tmp_path / "m.zip", header, [])
    with pytest.raises(ingest.HeaderError, match="ArrDelay, NASDelay"):
        ingest.read_month(path)


def test_read_month_types_rows_and_cause(tmp_path: Path) -> None:
    rows = [
        _row(),  # on time -> NONE
        _row(ArrDelay="45.00", ArrDel15="1.00", CarrierDelay="30.00", WeatherDelay="15.00"),
        _row(ArrDelay="40.00", ArrDel15="1.00", NASDelay="20.00", LateAircraftDelay="20.00"),
        _row(ArrDelay="20.00", ArrDel15="1.00", CarrierDelay="0.00"),  # delayed, no minutes
    ]
    path = _zip(tmp_path / "m.zip", [*ingest.COLUMNS, ""], [[*r, ""] for r in rows])
    table, source_rows = ingest.read_month(path)
    assert source_rows == table.num_rows == 4
    assert "Year" not in table.column_names and "Month" not in table.column_names
    assert table.schema.field("ArrDelay").type == pa.int32()
    assert table["ArrDelay"].to_pylist() == [-3, 45, 40, 20]
    assert table["primary_delay_cause"].to_pylist() == ["NONE", "Carrier", "TIE", "NONE"]


def test_render_rejects_unsafe_params(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "q.sql").write_text("select * from ontime where origin = '$origin'")
    monkeypatch.setattr(athena, "QUERIES", tmp_path)
    assert athena.render("q", {"origin": "SEA"}).endswith("'SEA'")
    with pytest.raises(ValueError, match="unsafe"):
        athena.render("q", {"origin": "x'; drop table ontime; --"})


def test_local_backend_reads_partitions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _zip(tmp_path / "m.zip", list(ingest.COLUMNS), [_row(), _row(Dest="SEA")])
    monkeypatch.setattr(ingest, "CURATED", tmp_path / "curated")
    ingest.ingest_month(path, 2023, 1)
    (tmp_path / "q.sql").write_text(
        "select year, month, dest, count(*) as n from ontime group by 1, 2, 3 order by dest"
    )
    monkeypatch.setattr(athena, "QUERIES", tmp_path)
    monkeypatch.setattr(athena, "CURATED_GLOB", (tmp_path / "curated/*/*/*.parquet").as_posix())
    df = athena.run_query("q", backend="local")
    assert df.to_dict("records") == [
        {"year": 2023, "month": 1, "dest": "SEA", "n": 1},
        {"year": 2023, "month": 1, "dest": "SFO", "n": 1},
    ]
