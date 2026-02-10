"""Tests for processor module."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import xarray as xr
import zarr

from nwpio.config import ProcessConfig
from nwpio.processor import GribProcessor


class TestZarrConsolidation:
    """Tests for zarr writing with post-write consolidation."""

    def test_write_zarr_with_consolidation_creates_zmetadata(self, tmp_path):
        """Test that _write_zarr_with_consolidation creates .zmetadata file."""
        # Create a simple dataset
        ds = xr.Dataset(
            {"temperature": (["time", "lat", "lon"], np.random.rand(2, 3, 4))},
            coords={
                "time": np.array(["2024-01-01", "2024-01-02"], dtype="datetime64[ns]"),
                "lat": [0, 1, 2],
                "lon": [0, 1, 2, 3],
            },
        )

        zarr_path = tmp_path / "test.zarr"

        config = ProcessConfig(
            grib_path="/tmp/grib",
            variables=["temperature"],
            zarr_path=str(zarr_path),
        )

        processor = GribProcessor(config=config)
        processor._write_zarr_with_consolidation(ds, str(zarr_path), mode="w")

        # Verify .zmetadata exists
        zmetadata_path = zarr_path / ".zmetadata"
        assert zmetadata_path.exists(), ".zmetadata should exist after consolidation"

    def test_write_zarr_with_consolidation_zmetadata_is_valid(self, tmp_path):
        """Test that .zmetadata contains valid consolidated metadata."""
        ds = xr.Dataset(
            {"wind_speed": (["time", "lat", "lon"], np.random.rand(2, 3, 4))},
            coords={
                "time": np.array(["2024-01-01", "2024-01-02"], dtype="datetime64[ns]"),
                "lat": [0, 1, 2],
                "lon": [0, 1, 2, 3],
            },
        )

        zarr_path = tmp_path / "test.zarr"

        config = ProcessConfig(
            grib_path="/tmp/grib",
            variables=["wind_speed"],
            zarr_path=str(zarr_path),
        )

        processor = GribProcessor(config=config)
        processor._write_zarr_with_consolidation(ds, str(zarr_path), mode="w")

        # Open with consolidated metadata and verify it works
        store = zarr.open(str(zarr_path), mode="r")
        assert "wind_speed" in store, (
            "Variable should be accessible via consolidated store"
        )

    def test_write_zarr_with_consolidation_can_be_opened_by_xarray(self, tmp_path):
        """Test that zarr written with consolidation can be opened by xarray."""
        ds = xr.Dataset(
            {"pressure": (["time", "lat", "lon"], np.random.rand(2, 3, 4))},
            coords={
                "time": np.array(["2024-01-01", "2024-01-02"], dtype="datetime64[ns]"),
                "lat": [0, 1, 2],
                "lon": [0, 1, 2, 3],
            },
        )

        zarr_path = tmp_path / "test.zarr"

        config = ProcessConfig(
            grib_path="/tmp/grib",
            variables=["pressure"],
            zarr_path=str(zarr_path),
        )

        processor = GribProcessor(config=config)
        processor._write_zarr_with_consolidation(ds, str(zarr_path), mode="w")

        # Open with xarray using consolidated metadata
        ds_loaded = xr.open_zarr(str(zarr_path), consolidated=True)
        assert "pressure" in ds_loaded.data_vars
        assert ds_loaded.sizes == {"time": 2, "lat": 3, "lon": 4}

    def test_zmetadata_written_after_data(self, tmp_path):
        """Test that .zmetadata is written after data files by checking modification times."""
        ds = xr.Dataset(
            {"humidity": (["time", "lat", "lon"], np.random.rand(2, 3, 4))},
            coords={
                "time": np.array(["2024-01-01", "2024-01-02"], dtype="datetime64[ns]"),
                "lat": [0, 1, 2],
                "lon": [0, 1, 2, 3],
            },
        )

        zarr_path = tmp_path / "test.zarr"

        config = ProcessConfig(
            grib_path="/tmp/grib",
            variables=["humidity"],
            zarr_path=str(zarr_path),
        )

        processor = GribProcessor(config=config)
        processor._write_zarr_with_consolidation(ds, str(zarr_path), mode="w")

        # Get modification time of .zmetadata
        zmetadata_path = zarr_path / ".zmetadata"
        zmetadata_mtime = zmetadata_path.stat().st_mtime

        # Check that .zmetadata was written after (or at same time as) all other files
        for file_path in zarr_path.rglob("*"):
            if file_path.is_file() and file_path.name != ".zmetadata":
                file_mtime = file_path.stat().st_mtime
                assert zmetadata_mtime >= file_mtime, (
                    f".zmetadata should be written after {file_path.name}"
                )

    def test_write_zarr_overwrite_mode(self, tmp_path):
        """Test that overwrite mode works correctly."""
        ds1 = xr.Dataset(
            {"var1": (["x"], [1, 2, 3])},
        )
        ds2 = xr.Dataset(
            {"var2": (["x"], [4, 5, 6])},
        )

        zarr_path = tmp_path / "test.zarr"

        config = ProcessConfig(
            grib_path="/tmp/grib",
            variables=["var1"],
            zarr_path=str(zarr_path),
            overwrite=True,
        )

        processor = GribProcessor(config=config)

        # Write first dataset
        processor._write_zarr_with_consolidation(ds1, str(zarr_path), mode="w")
        assert (zarr_path / ".zmetadata").exists()

        # Overwrite with second dataset
        processor._write_zarr_with_consolidation(ds2, str(zarr_path), mode="w")
        assert (zarr_path / ".zmetadata").exists()

        # Verify second dataset is present
        ds_loaded = xr.open_zarr(str(zarr_path), consolidated=True)
        assert "var2" in ds_loaded.data_vars
        assert "var1" not in ds_loaded.data_vars


class TestGCSUploadOrder:
    """Tests for GCS upload ordering (.zmetadata uploaded last)."""

    def test_upload_zarr_to_gcs_uploads_zmetadata_last(self, tmp_path):
        """Test that _upload_zarr_to_gcs uploads .zmetadata after all other files."""
        # Create a local zarr archive
        ds = xr.Dataset(
            {"temperature": (["time", "lat", "lon"], np.random.rand(2, 3, 4))},
            coords={
                "time": np.array(["2024-01-01", "2024-01-02"], dtype="datetime64[ns]"),
                "lat": [0, 1, 2],
                "lon": [0, 1, 2, 3],
            },
        )

        local_zarr_path = tmp_path / "test.zarr"
        ds.to_zarr(str(local_zarr_path), consolidated=False)
        zarr.consolidate_metadata(str(local_zarr_path))

        config = ProcessConfig(
            grib_path="/tmp/grib",
            variables=["temperature"],
            zarr_path="gs://test-bucket/test.zarr",
            verify_upload=False,  # Disable verification for mock test
        )

        processor = GribProcessor(config=config)

        # Track upload order
        upload_order = []

        # Mock the GCS client and bucket
        with patch("nwpio.utils.get_gcs_client") as mock_get_client:
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            mock_blob.upload_from_filename = lambda f, **kw: upload_order.append(
                Path(f).name
            )
            mock_bucket.blob.return_value = mock_blob
            mock_client.bucket.return_value = mock_bucket
            mock_get_client.return_value = mock_client

            processor._upload_zarr_to_gcs(local_zarr_path, "gs://test-bucket/test.zarr")

        # Verify .zmetadata was uploaded last
        assert len(upload_order) > 0, "Should have uploaded files"
        assert upload_order[-1] == ".zmetadata", (
            f".zmetadata should be last, got order: {upload_order}"
        )

    def test_upload_separates_zmetadata_from_parallel_batch(self, tmp_path):
        """Test that .zmetadata is not included in the parallel upload file list."""
        # Create a local zarr archive
        ds = xr.Dataset(
            {"var1": (["x"], [1, 2, 3])},
        )

        local_zarr_path = tmp_path / "test.zarr"
        ds.to_zarr(str(local_zarr_path), consolidated=False)
        zarr.consolidate_metadata(str(local_zarr_path))

        # Get all files and verify .zmetadata exists
        all_files = list(local_zarr_path.rglob("*"))
        all_file_names = [f.name for f in all_files if f.is_file()]
        assert ".zmetadata" in all_file_names, "Test setup: .zmetadata should exist"

        config = ProcessConfig(
            grib_path="/tmp/grib",
            variables=["var1"],
            zarr_path="gs://test-bucket/test.zarr",
            verify_upload=False,  # Disable verification for mock test
        )

        processor = GribProcessor(config=config)

        # Track files submitted to parallel executor
        parallel_batch_files = []
        zmetadata_uploaded_separately = False

        with patch("nwpio.utils.get_gcs_client") as mock_get_client:
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            mock_blob = MagicMock()

            def track_upload(filename, **kwargs):
                nonlocal zmetadata_uploaded_separately
                fname = Path(filename).name
                if fname == ".zmetadata":
                    # Check that parallel batch is already complete
                    zmetadata_uploaded_separately = len(parallel_batch_files) > 0

            mock_blob.upload_from_filename = track_upload
            mock_bucket.blob.return_value = mock_blob
            mock_client.bucket.return_value = mock_bucket
            mock_get_client.return_value = mock_client

            # Patch ThreadPoolExecutor to track what gets submitted
            original_executor = __import__(
                "concurrent.futures"
            ).futures.ThreadPoolExecutor

            class TrackingExecutor(original_executor):
                def submit(self, fn, f):
                    parallel_batch_files.append(f.name)
                    return super().submit(fn, f)

            with patch("concurrent.futures.ThreadPoolExecutor", TrackingExecutor):
                processor._upload_zarr_to_gcs(
                    local_zarr_path, "gs://test-bucket/test.zarr"
                )

        # .zmetadata should NOT be in the parallel batch
        assert ".zmetadata" not in parallel_batch_files, (
            ".zmetadata should not be in parallel batch"
        )
        # .zmetadata should be uploaded after parallel batch completes
        assert zmetadata_uploaded_separately, (
            ".zmetadata should be uploaded after parallel batch"
        )
