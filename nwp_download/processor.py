"""Process GRIB files and convert to Zarr format."""

import logging
from pathlib import Path
from typing import List, Optional

import fsspec
import xarray as xr
from tqdm import tqdm

from nwp_download.config import ProcessConfig
from nwp_download.utils import is_gcs_path, parse_gcs_path

logger = logging.getLogger(__name__)


class GribProcessor:
    """Process GRIB files and convert to Zarr."""

    def __init__(self, config: ProcessConfig):
        """
        Initialize processor.

        Args:
            config: Process configuration
        """
        self.config = config

    def process(self) -> str:
        """
        Process GRIB files and write to Zarr.

        Returns:
            Path to output Zarr archive
        """
        logger.info(f"Processing GRIB files from {self.config.grib_path}")
        logger.info(f"Extracting variables: {', '.join(self.config.variables)}")

        # Find all GRIB files
        grib_files = self._find_grib_files()
        logger.info(f"Found {len(grib_files)} GRIB files")

        if not grib_files:
            raise ValueError(f"No GRIB files found at {self.config.grib_path}")

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

        # Write to Zarr
        logger.info(f"Writing to Zarr: {self.config.output_path}")
        self._write_zarr(combined_ds)

        logger.info("Processing complete")
        return self.config.output_path

    def _find_grib_files(self) -> List[str]:
        """
        Find all GRIB files in the specified path.

        Returns:
            List of GRIB file paths
        """
        grib_path = self.config.grib_path

        if is_gcs_path(grib_path):
            # Use fsspec to list GCS files
            fs = fsspec.filesystem("gs")
            # Remove gs:// prefix for fsspec
            path = grib_path.replace("gs://", "")

            # Check if path is a file or directory
            if fs.isfile(path):
                return [grib_path]
            elif fs.isdir(path):
                # Find all GRIB files recursively
                all_files = fs.glob(f"{path}/**/*.grib*")
                all_files.extend(fs.glob(f"{path}/**/*.grb*"))
                return [f"gs://{f}" for f in all_files]
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
                grib_files = list(path.glob("**/*.grib*"))
                grib_files.extend(path.glob("**/*.grb*"))
                return [str(f) for f in grib_files]
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
            ds = xr.open_dataset(
                file_path,
                engine="cfgrib",
                backend_kwargs=backend_kwargs,
            )

            # Ensure time dimension exists
            if "time" not in ds.dims:
                if "valid_time" in ds.coords:
                    ds = ds.rename({"valid_time": "time"})
                elif "time" in ds.coords:
                    ds = ds.expand_dims("time")

            return ds

        except Exception as e:
            logger.error(f"Failed to load {file_path}: {e}")
            return None

    def _write_zarr(self, dataset: xr.Dataset) -> None:
        """
        Write dataset to Zarr format.

        Args:
            dataset: xarray Dataset to write
        """
        # Configure encoding
        encoding = {}
        for var in dataset.data_vars:
            encoding[var] = {"compressor": self._get_compressor()}

        # Write mode
        mode = "w" if self.config.overwrite else "w-"

        # Write to Zarr
        if is_gcs_path(self.config.output_path):
            # Write to GCS using gcsfs
            dataset.to_zarr(
                self.config.output_path,
                mode=mode,
                encoding=encoding,
                consolidated=True,
            )
        else:
            # Write to local filesystem
            output_path = Path(self.config.output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            dataset.to_zarr(
                output_path,
                mode=mode,
                encoding=encoding,
                consolidated=True,
            )

    def _get_compressor(self):
        """Get compressor for Zarr encoding."""
        import zarr

        if self.config.compression == "default":
            return zarr.Blosc(cname="zstd", clevel=3, shuffle=zarr.Blosc.SHUFFLE)
        elif self.config.compression == "zstd":
            return zarr.Blosc(cname="zstd", clevel=5, shuffle=zarr.Blosc.SHUFFLE)
        elif self.config.compression == "lz4":
            return zarr.Blosc(cname="lz4", clevel=5, shuffle=zarr.Blosc.SHUFFLE)
        elif self.config.compression == "none":
            return None
        else:
            logger.warning(f"Unknown compression: {self.config.compression}, using default")
            return zarr.Blosc(cname="zstd", clevel=3, shuffle=zarr.Blosc.SHUFFLE)

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
