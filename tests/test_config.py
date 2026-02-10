"""Tests for configuration models."""

import pytest
from datetime import datetime
from nwpio.config import DownloadConfig, ProcessConfig, WorkflowConfig


def test_download_config_valid():
    """Test valid download configuration."""
    config = DownloadConfig(
        product="gfs",
        resolution="0p25",
        cycle=datetime(2024, 1, 1, 0),  # 00z cycle
        max_lead_time=120,
        source_bucket="source-bucket",
        destination_bucket="dest-bucket",
    )
    assert config.product == "gfs"
    assert config.max_lead_time == 120
    assert config.cycle.hour == 0


def test_download_config_invalid_cycle():
    """Test invalid cycle for ECMWF."""
    with pytest.raises(ValueError, match="ECMWF only supports"):
        DownloadConfig(
            product="ecmwf-hres",
            resolution="0p1",
            cycle=datetime(2024, 1, 1, 6),  # 06z - Invalid for ECMWF
            max_lead_time=120,
            source_bucket="source-bucket",
            destination_bucket="dest-bucket",
        )


def test_download_config_invalid_lead_time():
    """Test invalid lead time for GFS."""
    with pytest.raises(ValueError, match="GFS max lead time"):
        DownloadConfig(
            product="gfs",
            resolution="0p25",
            cycle=datetime(2024, 1, 1, 0),
            max_lead_time=500,  # Exceeds GFS limit
            source_bucket="source-bucket",
            destination_bucket="dest-bucket",
        )


def test_process_config_valid():
    """Test valid process configuration."""
    config = ProcessConfig(
        grib_path="gs://bucket/grib/",
        variables=["t2m", "u10", "v10"],
        zarr_path="gs://bucket/output.zarr",
    )
    assert len(config.variables) == 3
    assert config.write_local_first is True


def test_workflow_config():
    """Test workflow configuration."""
    download_config = DownloadConfig(
        product="gfs",
        resolution="0p25",
        cycle=datetime(2024, 1, 1, 0),
        max_lead_time=120,
        source_bucket="source-bucket",
        destination_bucket="dest-bucket",
    )

    process_config = ProcessConfig(
        grib_path="gs://bucket/grib/",
        variables=["t2m"],
        zarr_path="gs://bucket/output.zarr",
    )

    workflow_config = WorkflowConfig(
        download=download_config,
        process={
            "default": process_config
        },  # process expects a dict with named configs
        cleanup_grib=True,
    )

    assert workflow_config.cleanup_grib is True
    assert workflow_config.download.product == "gfs"
