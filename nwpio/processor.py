"""Process GRIB files and convert to Zarr format."""

import logging
from pathlib import Path
from typing import List, Optional

import fsspec
import xarray as xr
from tqdm import tqdm

from nwpio.config import ProcessConfig
from nwpio.utils import is_gcs_path, parse_gcs_path

logger = logging.getLogger(__name__)


class GribProcessor:
    """Process GRIB files and convert to Zarr."""

    def __init__(self, config: ProcessConfig, cycle: Optional[str] = None):
        """
        Initialize processor.

        Args:
            config: Process configuration
            cycle: Optional cycle datetime for path formatting
        """
        self.config = config
        self.cycle = cycle
        logger.debug(
            f"GribProcessor initialized with cycle: {cycle} (type: {type(cycle)})"
        )

    def process(self) -> str:
        """
        Process GRIB files and write to Zarr.

        Returns:
            Path to output Zarr archive
        """
        formatted_path = self._format_grib_path()
        logger.info(f"Processing GRIB files from {formatted_path}")
        logger.info(f"Extracting variables: {', '.join(self.config.variables)}")

        # Find all GRIB files
        grib_files = self._find_grib_files()
        logger.info(f"Found {len(grib_files)} GRIB files")

        if not grib_files:
            raise ValueError(f"No GRIB files found at {formatted_path}")

        # Load and process GRIB files
        if self.config.max_grib_workers > 1:
            # Parallel loading
            logger.info(
                f"Loading GRIB files with {self.config.max_grib_workers} workers..."
            )
            datasets = self._load_grib_files_parallel(grib_files)
        else:
            # Sequential loading
            datasets = []
            for grib_file in tqdm(grib_files, desc="Loading GRIB files"):
                try:
                    ds = self._load_grib_file(grib_file)
                    if ds is not None:
                        datasets.append(ds)
                except Exception as e:
                    raise RuntimeError(f"Failed to load {grib_file}: {e}")

        if not datasets:
            raise ValueError("No datasets could be loaded from GRIB files")

        # Combine datasets along time dimension
        logger.info("Combining datasets...")
        combined_ds = xr.concat(datasets, dim="time")
        combined_ds = combined_ds.sortby("time")

        # Filter to requested variables
        available_vars = set(combined_ds.data_vars)
        requested_vars = set(self.config.variables)
        missing_vars = requested_vars - available_vars

        if missing_vars:
            logger.warning(f"Variables not found in GRIB files: {missing_vars}")

        vars_to_extract = list(requested_vars & available_vars)
        if not vars_to_extract:
            raise ValueError("None of the requested variables found in GRIB files")

        combined_ds = combined_ds[vars_to_extract]

        # Clean coordinates if requested
        if self.config.clean_coords:
            logger.info("Cleaning dataset coordinates...")
            combined_ds = self._clean_dataset(combined_ds)

        # Rename variables if requested
        if self.config.rename_vars:
            logger.info(f"Renaming variables: {self.config.rename_vars}")
            combined_ds = combined_ds.rename(self.config.rename_vars)

        # Apply chunking if specified
        if self.config.chunks:
            logger.info(f"Applying chunking: {self.config.chunks}")
            combined_ds = combined_ds.chunk(self.config.chunks)
        else:
            # Default chunking strategy
            default_chunks = {"time": 1}
            logger.info(f"Applying default chunking: {default_chunks}")
            combined_ds = combined_ds.chunk(default_chunks)

        # Format zarr path with timestamps
        zarr_path = self._format_zarr_path(combined_ds)
        logger.info(f"Writing to Zarr: {zarr_path}")
        self._write_zarr(combined_ds, zarr_path)

        logger.info("Processing complete")
        return zarr_path

    def _clean_dataset(self, dataset: xr.Dataset) -> xr.Dataset:
        """
        Clean dataset by removing non-dimensional coordinates.

        Keeps only dimensional coordinates (time, latitude, longitude)
        and drops all non-dimensional coordinates (GRIB metadata).

        Args:
            dataset: Input xarray Dataset

        Returns:
            Cleaned xarray Dataset with only dimensional coordinates
        """
        # Reset all non-dimensional coordinates (drops GRIB metadata)
        dataset = dataset.reset_coords(drop=True)

        logger.info(
            f"Cleaned dataset - coords: {list(dataset.coords.keys())}, vars: {list(dataset.data_vars.keys())}"
        )

        return dataset

    def _find_grib_files(self) -> List[str]:
        """
        Find all GRIB files in the specified path.

        Returns:
            List of GRIB file paths
        """
        grib_path = self._format_grib_path()

        if not grib_path:
            raise ValueError(
                "grib_path is not set. Either provide it in config or run download step first."
            )

        if is_gcs_path(grib_path):
            # Use fsspec to list GCS files
            fs = fsspec.filesystem("gs")
            # Remove gs:// prefix and trailing slash for fsspec
            path = grib_path.replace("gs://", "").rstrip("/")

            # Check if path is a file or directory
            if fs.isfile(path):
                return [grib_path]
            elif fs.isdir(path):
                # Find all GRIB files (both with and without extensions)
                all_files = []
                # Standard GRIB extensions
                all_files.extend(fs.glob(f"{path}/*.grib*"))
                all_files.extend(fs.glob(f"{path}/*.grb*"))
                # GFS/ECMWF files without extension
                all_files.extend(fs.glob(f"{path}/gfs.*"))
                all_files.extend(fs.glob(f"{path}/ecmwf.*"))
                return [f"gs://{f}" for f in sorted(set(all_files))]
            else:
                # Try glob pattern
                files = fs.glob(path)
                return [f"gs://{f}" for f in files]
        else:
            # Local filesystem
            path = Path(grib_path)
            if path.is_file():
                return [str(path)]
            elif path.is_dir():
                # Find all GRIB files (both with and without extensions)
                grib_files = []
                # Standard GRIB extensions
                grib_files.extend(path.glob("*.grib*"))
                grib_files.extend(path.glob("*.grb*"))
                # GFS/ECMWF files without extension
                grib_files.extend(path.glob("gfs.*"))
                grib_files.extend(path.glob("ecmwf.*"))
                return [str(f) for f in sorted(set(grib_files))]
            else:
                # Path doesn't exist
                raise FileNotFoundError(
                    f"GRIB path does not exist: {grib_path}\n"
                    f"Make sure to run the download step first or provide a valid grib_path."
                )

    def _load_grib_files_parallel(self, grib_files: List[str]) -> List[xr.Dataset]:
        """
        Load multiple GRIB files in parallel.

        Args:
            grib_files: List of GRIB file paths

        Returns:
            List of loaded xarray Datasets

        Raises:
            RuntimeError: If any file fails to load
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        datasets = []
        failed_files = []

        with ThreadPoolExecutor(max_workers=self.config.max_grib_workers) as executor:
            # Submit all files for loading
            future_to_file = {
                executor.submit(self._load_grib_file, grib_file): grib_file
                for grib_file in grib_files
            }

            # Collect results with progress bar
            with tqdm(total=len(grib_files), desc="Loading GRIB files") as pbar:
                for future in as_completed(future_to_file):
                    grib_file = future_to_file[future]
                    try:
                        ds = future.result()
                        if ds is not None:
                            datasets.append(ds)
                        else:
                            failed_files.append((grib_file, "Returned None"))
                    except Exception as e:
                        failed_files.append((grib_file, str(e)))
                    pbar.update(1)

        # Report any failures
        if failed_files:
            error_summary = "\n".join([f"  - {f}: {err}" for f, err in failed_files])
            raise RuntimeError(
                f"Failed to load {len(failed_files)}/{len(grib_files)} GRIB files:\n{error_summary}"
            )

        return datasets

    def _load_grib_file(self, file_path: str) -> Optional[xr.Dataset]:
        """
        Load a single GRIB file using cfgrib.

        Args:
            file_path: Path to GRIB file

        Returns:
            xarray Dataset or None if loading fails
        """
        try:
            # Build backend kwargs
            backend_kwargs = {"indexpath": ""}  # Disable index caching

            if self.config.filter_by_keys:
                backend_kwargs["filter_by_keys"] = self.config.filter_by_keys

            # Load with cfgrib engine
            # For GCS paths, we need to use fsspec to open the file
            if is_gcs_path(file_path):
                import tempfile
                import shutil

                # Download to temp file since cfgrib doesn't support GCS directly
                fs = fsspec.filesystem("gs")
                gcs_path = file_path.replace("gs://", "")

                with tempfile.NamedTemporaryFile(delete=False, suffix=".grib") as tmp:
                    with fs.open(gcs_path, "rb") as f:
                        shutil.copyfileobj(f, tmp)
                    tmp_path = tmp.name

                try:
                    ds = xr.open_dataset(
                        tmp_path,
                        engine="cfgrib",
                        chunks="auto",
                        backend_kwargs=backend_kwargs,
                    )
                    # Load into memory so we can delete the temp file
                    ds = ds.load()
                finally:
                    import os

                    os.unlink(tmp_path)
            else:
                ds = xr.open_dataset(
                    file_path,
                    engine="cfgrib",
                    chunks="auto",
                    backend_kwargs=backend_kwargs,
                )

            # Ensure time dimension exists and uses valid_time (forecast valid time)
            # GRIB files have both 'time' (reference/cycle time) and 'valid_time' (forecast time)
            # We want valid_time as our time dimension
            if "valid_time" in ds.coords:
                # Drop the reference time coordinate first if it exists as a non-dimension coord
                if "time" in ds.coords and "time" not in ds.dims:
                    ds = ds.drop_vars("time")

                # Use valid_time as the time dimension
                if "valid_time" not in ds.dims:
                    ds = ds.expand_dims("valid_time")

                # Rename to 'time' for consistency
                ds = ds.rename({"valid_time": "time"})
            elif "time" not in ds.dims:
                # Fallback: if only 'time' exists, expand it as dimension
                if "time" in ds.coords:
                    ds = ds.expand_dims("time")

            return ds

        except Exception as e:
            logger.error(f"Failed to load {file_path}: {e}")
            return None

    def _format_grib_path(self) -> str:
        """
        Format grib_path with cycle information if provided.

        Supports {cycle:...} format strings:
        - {cycle:%Y%m%d} -> 20240101
        - {cycle:%Hz} -> 00z
        - {cycle:%H} -> 00

        Returns:
            Formatted grib path
        """
        grib_path = self.config.grib_path

        # Check if there are any placeholders
        if "{" not in grib_path:
            return grib_path

        # Check if cycle is provided
        if not self.cycle:
            logger.warning(
                f"grib_path contains placeholders but no cycle provided: {grib_path}"
            )
            return grib_path

        import re
        from datetime import datetime

        # Parse cycle if it's a string, otherwise use as datetime
        if isinstance(self.cycle, str):
            dt = datetime.fromisoformat(self.cycle)
        elif isinstance(self.cycle, datetime):
            dt = self.cycle
        else:
            logger.warning(f"Invalid cycle type: {type(self.cycle)}")
            return grib_path

        # Handle {cycle:...} format strings
        cycle_pattern = r"\{cycle:([^}]+)\}"
        matches = re.finditer(cycle_pattern, grib_path)
        for match in matches:
            format_str = match.group(1)
            formatted_value = dt.strftime(format_str)
            grib_path = grib_path.replace(match.group(0), formatted_value)

        logger.debug(f"Formatted grib_path: {grib_path}")
        return grib_path

    def _format_zarr_path(self, dataset: xr.Dataset) -> str:
        """
        Format zarr path with cycle datetime placeholders.

        Supports Python datetime formatting syntax:
        - {cycle:%Y%m%d} -> 20240101
        - {cycle:%Hz} -> 00z, 06z, etc.
        - {cycle:%Y-%m-%d_%H%M} -> 2024-01-01_0000

        Also supports legacy placeholders for backward compatibility:
        - {date} -> 20240101
        - {time} -> 000000
        - {timestamp} -> custom format from config

        Args:
            dataset: xarray Dataset (used to extract time information)

        Returns:
            Formatted zarr path
        """
        zarr_path = self.config.zarr_path

        # Check if there are any placeholders
        if "{" not in zarr_path:
            return zarr_path

        # Extract first time from dataset for timestamp
        if "time" in dataset.coords:
            first_time = dataset.time.values[0]
            # Convert numpy datetime64 to Python datetime
            import pandas as pd
            import re

            dt = pd.Timestamp(first_time).to_pydatetime()

            # Handle {cycle:...} format strings
            # Find all {cycle:format} patterns and replace them
            cycle_pattern = r"\{cycle:([^}]+)\}"
            matches = re.finditer(cycle_pattern, zarr_path)
            for match in matches:
                format_str = match.group(1)
                formatted_value = dt.strftime(format_str)
                zarr_path = zarr_path.replace(match.group(0), formatted_value)

            # Handle legacy placeholders for backward compatibility
            legacy_replacements = {
                "{timestamp}": dt.strftime(self.config.timestamp_format),
                "{date}": dt.strftime("%Y%m%d"),
                "{time}": dt.strftime("%H%M%S"),
                "{cycle}": f"{dt.hour:02d}z",
            }

            for placeholder, value in legacy_replacements.items():
                zarr_path = zarr_path.replace(placeholder, value)

        return zarr_path

    def _write_zarr(self, dataset: xr.Dataset, zarr_path: str) -> None:
        """
        Write dataset to Zarr format.

        Args:
            dataset: xarray Dataset to write
            zarr_path: Output path for Zarr archive
        """
        # Write mode
        mode = "w" if self.config.overwrite else "w-"

        # Determine if we need to write locally first then upload
        if is_gcs_path(zarr_path) and self.config.write_local_first:
            self._write_local_then_upload(dataset, zarr_path, mode)
        elif is_gcs_path(zarr_path):
            # Write directly to GCS
            logger.info("Writing directly to GCS...")
            dataset.to_zarr(
                zarr_path,
                mode=mode,
                consolidated=True,
            )
        else:
            # Write to local filesystem
            logger.info(f"Writing to local filesystem: {zarr_path}")
            local_path = Path(zarr_path)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            dataset.to_zarr(
                local_path,
                mode=mode,
                consolidated=True,
            )

    def _write_local_then_upload(
        self, dataset: xr.Dataset, gcs_path: str, mode: str
    ) -> None:
        """
        Write Zarr to local temp directory, then upload to GCS.

        Args:
            dataset: xarray Dataset to write
            gcs_path: Final GCS destination path
            mode: Write mode ('w' or 'w-')
        """
        import tempfile
        import shutil
        import fsspec

        # Check if destination exists when mode is 'w-'
        if mode == "w-":
            fs = fsspec.filesystem("gs")
            bucket_name, blob_prefix = parse_gcs_path(gcs_path)
            gcs_check_path = f"{bucket_name}/{blob_prefix}"

            if fs.exists(gcs_check_path):
                raise FileExistsError(
                    f"Zarr archive already exists at {gcs_path}. "
                    "Set overwrite=true to replace it."
                )

        # Determine temp directory
        if self.config.local_temp_dir:
            temp_base = Path(self.config.local_temp_dir)
            temp_base.mkdir(parents=True, exist_ok=True)
            temp_dir = tempfile.mkdtemp(dir=temp_base)
        else:
            temp_dir = tempfile.mkdtemp()

        temp_path = Path(temp_dir)
        zarr_name = Path(gcs_path).name
        local_zarr_path = temp_path / zarr_name

        try:
            # Write to local temp directory
            logger.info(f"Writing to local temp directory: {local_zarr_path}")
            dataset.to_zarr(
                str(local_zarr_path),
                mode="w",  # Always overwrite in temp
                consolidated=True,
            )

            # Delete existing Zarr if overwrite=true
            if mode == "w":
                fs = fsspec.filesystem("gs")
                bucket_name, blob_prefix = parse_gcs_path(gcs_path)
                gcs_check_path = f"{bucket_name}/{blob_prefix}"

                if fs.exists(gcs_check_path):
                    logger.info(f"Deleting existing Zarr archive: {gcs_path}")
                    fs.rm(gcs_check_path, recursive=True)

            # Upload to GCS
            logger.info(f"Uploading to GCS: {gcs_path}")
            self._upload_zarr_to_gcs(local_zarr_path, gcs_path)

            logger.info("Upload complete successfully")

        finally:
            # Clean up temp directory
            logger.info(f"Cleaning up temp directory: {temp_dir}")
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _upload_zarr_to_gcs(self, local_zarr_path: Path, gcs_path: str) -> None:
        """
        Upload a local Zarr archive to GCS using parallel uploads with retry logic.

        Args:
            local_zarr_path: Local path to Zarr archive
            gcs_path: GCS destination path

        Raises:
            RuntimeError: If any files fail to upload after retries
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from nwpio.utils import get_gcs_client
        import time

        bucket_name, blob_prefix = parse_gcs_path(gcs_path)
        client = get_gcs_client()
        bucket = client.bucket(bucket_name)

        # Get all files to upload
        zarr_files = [f for f in local_zarr_path.rglob("*") if f.is_file()]
        logger.info(f"Uploading {len(zarr_files)} files...")

        from tqdm import tqdm

        def upload_file_with_retry(local_file: Path) -> tuple[str, bool, str]:
            """
            Upload a single file to GCS with retry logic.

            Returns:
                Tuple of (blob_name, success, error_message)
            """
            relative_path = local_file.relative_to(local_zarr_path)
            blob_name = f"{blob_prefix}/{relative_path}".replace("\\", "/")
            blob = bucket.blob(
                blob_name, chunk_size=5 * 1024 * 1024
            )  # 5MB chunks for resumable upload

            max_retries = self.config.upload_max_retries
            timeout = self.config.upload_timeout

            for attempt in range(max_retries):
                try:
                    blob.upload_from_filename(
                        str(local_file),
                        timeout=timeout,
                        checksum="md5",
                    )
                    return blob_name, True, ""
                except Exception as e:
                    error_msg = str(e)
                    if attempt < max_retries - 1:
                        # Exponential backoff: 2^attempt seconds
                        wait_time = 2**attempt
                        logger.warning(
                            f"Upload failed for {relative_path} (attempt {attempt + 1}/{max_retries}): {error_msg}. "
                            f"Retrying in {wait_time}s..."
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"Upload failed for {relative_path} after {max_retries} attempts: {error_msg}"
                        )
                        return blob_name, False, error_msg

            return blob_name, False, "Max retries exceeded"

        # Upload files in parallel
        max_workers = self.config.max_upload_workers
        logger.info(
            f"Using {max_workers} parallel workers for upload (timeout: {self.config.upload_timeout}s)"
        )

        failed_uploads = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(upload_file_with_retry, f): f for f in zarr_files
            }

            with tqdm(total=len(zarr_files), desc="Uploading to GCS") as pbar:
                for future in as_completed(futures):
                    blob_name, success, error_msg = future.result()
                    if success:
                        pbar.update(1)
                    else:
                        local_file = futures[future]
                        failed_uploads.append((local_file, error_msg))
                        pbar.update(1)

        # Report failed uploads
        if failed_uploads:
            error_summary = "\n".join([f"  - {f}: {err}" for f, err in failed_uploads])
            raise RuntimeError(
                f"Failed to upload {len(failed_uploads)}/{len(zarr_files)} files:\n{error_summary}"
            )

        # Verify upload if enabled
        if self.config.verify_upload:
            logger.info("Verifying upload...")
            self._verify_zarr_upload(local_zarr_path, gcs_path)

    def _verify_zarr_upload(self, local_zarr_path: Path, gcs_path: str) -> None:
        """
        Verify that all local files were uploaded to GCS.

        Args:
            local_zarr_path: Local path to Zarr archive
            gcs_path: GCS destination path

        Raises:
            RuntimeError: If any files are missing from GCS
        """
        import fsspec

        bucket_name, blob_prefix = parse_gcs_path(gcs_path)
        fs = fsspec.filesystem("gs")

        # Get all local files
        local_files = [f for f in local_zarr_path.rglob("*") if f.is_file()]

        # Check each file exists in GCS
        missing_files = []
        for local_file in local_files:
            relative_path = local_file.relative_to(local_zarr_path)
            gcs_file_path = f"{bucket_name}/{blob_prefix}/{relative_path}".replace(
                "\\", "/"
            )

            if not fs.exists(gcs_file_path):
                missing_files.append(str(relative_path))

        if missing_files:
            error_summary = "\n".join([f"  - {f}" for f in missing_files])
            raise RuntimeError(
                f"Upload verification failed: {len(missing_files)}/{len(local_files)} files missing from GCS:\n{error_summary}"
            )

        logger.info(
            f"Upload verification successful: all {len(local_files)} files present in GCS"
        )

    def inspect_grib_files(self) -> dict:
        """
        Inspect GRIB files and return metadata.

        Returns:
            Dictionary with GRIB file metadata
        """
        grib_files = self._find_grib_files()

        if not grib_files:
            return {"error": "No GRIB files found"}

        # Load first file to get metadata
        first_file = grib_files[0]
        try:
            ds = xr.open_dataset(first_file, engine="cfgrib")

            return {
                "num_files": len(grib_files),
                "variables": list(ds.data_vars),
                "dimensions": dict(ds.dims),
                "coordinates": list(ds.coords),
                "sample_file": first_file,
            }
        except Exception as e:
            return {"error": f"Failed to inspect GRIB files: {e}"}
