"""Tests for ECMWF data source discovery."""

from datetime import datetime
from unittest.mock import patch

import pytest

from nwpio.sources import ECMWFSource

BUCKET = "ecmwf-open-data"
PREFIX = f"{BUCKET}/20261021/00z/ifs/0p1/oper"


def make_source(max_lead_time, file_type="sfc"):
    return ECMWFSource(
        product="ecmwf-hres",
        resolution="0p1",
        cycle=datetime(2026, 10, 21, 0),
        max_lead_time=max_lead_time,
        source_bucket=BUCKET,
        destination_bucket=None,
        local_download_dir="/tmp",
        source_type="gcs",
        file_type=file_type,
    )


def listing(lead_times):
    files = []
    for lt in lead_times:
        for kind in ("sfc", "pl"):
            name = f"20261021000000-{lt}h-oper-fc-{kind}"
            files += [f"{PREFIX}/{name}.grib2", f"{PREFIX}/{name}.index"]
    return files


def test_lead_times():
    assert make_source(12)._generate_lead_times() == [0, 3, 6, 9, 12]
    lead_times = make_source(360)._generate_lead_times()
    assert len(lead_times) == 85
    assert lead_times[48:50] == [144, 150]


@pytest.mark.parametrize("file_type", ["sfc", "pl"])
def test_discovers_file_type(file_type):
    with patch("fsspec.filesystem") as fs:
        fs.return_value.ls.return_value = listing(range(0, 13, 3))
        files = make_source(12, file_type).get_file_list()
    assert [f.lead_time for f in files] == [0, 3, 6, 9, 12]
    assert all(f.source_path.endswith(f"-{file_type}.grib2") for f in files)
    assert all(f"0p1-{file_type}.f" in f.destination_path for f in files)


def test_incomplete_cycle_raises():
    with patch("fsspec.filesystem") as fs:
        fs.return_value.ls.return_value = listing([0, 3, 9, 12])
        with pytest.raises(FileNotFoundError, match=r"missing up to 12h: \[6\]"):
            make_source(12).get_file_list()


def test_unpublished_cycle_raises():
    with patch("fsspec.filesystem") as fs:
        fs.return_value.ls.side_effect = FileNotFoundError
        with pytest.raises(FileNotFoundError, match="5 lead times missing"):
            make_source(12).get_file_list()
