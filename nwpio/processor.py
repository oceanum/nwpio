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
        logger.debug(f"GribProcessor initialized with cycle: {cycle} (type: {type(cycle)})")

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
        datasets = []
        for grib_file in tqdm(grib_files, desc="Loading GRIB files"):
            try:
                ds = self._load_grib_file(grib_file)
                if ds is not None:
                    datasets.append(ds)
            except Exception as e:
                logger.error(f"Failed to load {grib_file}: {e}")

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

        # Apply chunking if specified
        if self.config.chunks:
            logger.info(f"Applying chunking: {self.config.chunks}")
            combined_ds = combined_ds.chunk(self.config.chunks)
        else:
            # Default chunking strategy
            default_chunks = {"time": 1}
            logger.info(f"Applying default chunking: {default_chunks}")
            combined_ds = combined_ds.chunk(default_chunks)

        # Format output path with timestamps
        output_path = self._format_output_path(combined_ds)
        logger.info(f"Writing to Zarr: {output_path}")
        self._write_zarr(combined_ds, output_path)

        logger.info("Processing complete")
        return output_path

    def _find_grib_files(self) -> List[str]:
        """
        Find all GRIB files in the specified path.

        Returns:
            List of GRIB file paths
        """
        grib_path = self._format_grib_path()
        
        if not grib_path:
            raise ValueError("grib_path is not set. Either provide it in config or run download step first.")

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
                # Try glob pattern
                return [str(f) for f in Path(".").glob(grib_path)]

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
                    backend_kwargs=backend_kwargs,
                )

            # Ensure time dimension exists
            if "time" not in ds.dims:
                if "valid_time" in ds.coords and "time" not in ds.coords:
                    # Rename valid_time to time if time doesn't exist
                    ds = ds.rename({"valid_time": "time"})
                elif "time" in ds.coords:
                    # Expand time coordinate to dimension
                    ds = ds.expand_dims("time")
                elif "valid_time" in ds.coords:
                    # Use valid_time as time dimension
                    ds = ds.expand_dims("valid_time").rename({"valid_time": "time"})

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
            logger.warning(f"grib_path contains placeholders but no cycle provided: {grib_path}")
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

    def _format_output_path(self, dataset: xr.Dataset) -> str:
        """
        Format output path with cycle datetime placeholders.

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
            Formatted output path
        """
        output_path = self.config.output_path

        # Check if there are any placeholders
        if "{" not in output_path:
            return output_path

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
            matches = re.finditer(cycle_pattern, output_path)
            for match in matches:
                format_str = match.group(1)
                formatted_value = dt.strftime(format_str)
                output_path = output_path.replace(match.group(0), formatted_value)

            # Handle legacy placeholders for backward compatibility
            legacy_replacements = {
                "{timestamp}": dt.strftime(self.config.timestamp_format),
                "{date}": dt.strftime("%Y%m%d"),
                "{time}": dt.strftime("%H%M%S"),
                "{cycle}": f"{dt.hour:02d}z",
            }

            for placeholder, value in legacy_replacements.items():
                output_path = output_path.replace(placeholder, value)

        return output_path

    def _write_zarr(self, dataset: xr.Dataset, output_path: str) -> None:
        """
        Write dataset to Zarr format.

        Args:
            dataset: xarray Dataset to write
            output_path: Output path for Zarr archive
        """
        # Write mode
        mode = "w" if self.config.overwrite else "w-"

        # Determine if we need to write locally first then upload
        if is_gcs_path(output_path) and self.config.write_local_first:
            self._write_local_then_upload(dataset, output_path, mode)
        elif is_gcs_path(output_path):
            # Write directly to GCS
            logger.info("Writing directly to GCS...")
            dataset.to_zarr(
                output_path,
                mode=mode,
                consolidated=True,
            )
        else:
            # Write to local filesystem
            logger.info(f"Writing to local filesystem: {output_path}")
            local_path = Path(output_path)
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

            logger.info("Upload complete")

        finally:
            # Clean up temp directory
            logger.info(f"Cleaning up temp directory: {temp_dir}")
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _upload_zarr_to_gcs(self, local_zarr_path: Path, gcs_path: str) -> None:
        """
        Upload a local Zarr archive to GCS using parallel uploads.

        Args:
            local_zarr_path: Local path to Zarr archive
            gcs_path: GCS destination path
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from nwpio.utils import get_gcs_client

        bucket_name, blob_prefix = parse_gcs_path(gcs_path)
        client = get_gcs_client()
        bucket = client.bucket(bucket_name)

        # Get all files to upload
        zarr_files = [f for f in local_zarr_path.rglob("*") if f.is_file()]
        logger.info(f"Uploading {len(zarr_files)} files...")

        from tqdm import tqdm

        def upload_file(local_file: Path) -> str:
            """Upload a single file to GCS."""
            relative_path = local_file.relative_to(local_zarr_path)
            blob_name = f"{blob_prefix}/{relative_path}".replace("\\", "/")
            blob = bucket.blob(blob_name)
            blob.upload_from_filename(str(local_file))
            return blob_name

        # Upload files in parallel
        max_workers = self.config.max_upload_workers
        logger.info(f"Using {max_workers} parallel workers for upload")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(upload_file, f): f for f in zarr_files}
            
            with tqdm(total=len(zarr_files), desc="Uploading to GCS") as pbar:
                for future in as_completed(futures):
                    try:
                        future.result()
                        pbar.update(1)
                    except Exception as e:
                        local_file = futures[future]
                        logger.error(f"Failed to upload {local_file}: {e}")

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
