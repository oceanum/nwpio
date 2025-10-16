"""GRIB file downloader from cloud archives."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional

from google.cloud import storage
from tqdm import tqdm

from nwpio.config import DownloadConfig
from nwpio.sources import GribFileSpec, create_data_source
from nwpio.utils import (
    copy_gcs_blob,
    gcs_blob_exists,
    get_gcs_client,
    parse_gcs_path,
)

logger = logging.getLogger(__name__)


class GribDownloader:
    """Download GRIB files from cloud archives to GCS."""

    def __init__(self, config: DownloadConfig, max_workers: int = 10):
        """
        Initialize downloader.

        Args:
            config: Download configuration
            max_workers: Maximum number of parallel download workers
        """
        self.config = config
        self.max_workers = max_workers
        self.client = get_gcs_client()
        self.data_source = create_data_source(
            product=config.product,
            resolution=config.resolution,
            cycle=config.cycle,
            max_lead_time=config.max_lead_time,
            source_bucket=config.source_bucket,
            destination_bucket=config.destination_bucket,
            destination_prefix=config.destination_prefix or "",
        )

    def download(self) -> List[str]:
        """
        Download all GRIB files for the configured forecast.

        Returns:
            List of downloaded file paths
        """
        file_specs = self.data_source.get_file_list()
        logger.info(f"Found {len(file_specs)} files to download")

        downloaded_files = []
        failed_files = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all download tasks
            future_to_spec = {
                executor.submit(self._download_file, spec): spec
                for spec in file_specs
            }

            # Process completed downloads with progress bar
            with tqdm(total=len(file_specs), desc="Downloading GRIB files") as pbar:
                for future in as_completed(future_to_spec):
                    spec = future_to_spec[future]
                    try:
                        success, dest_path = future.result()
                        if success:
                            downloaded_files.append(dest_path)
                        else:
                            failed_files.append(spec.source_path)
                    except Exception as e:
                        logger.error(f"Error downloading {spec.source_path}: {e}")
                        failed_files.append(spec.source_path)
                    finally:
                        pbar.update(1)

        # Log summary
        logger.info(f"Successfully downloaded {len(downloaded_files)} files")
        if failed_files:
            logger.warning(f"Failed to download {len(failed_files)} files")
            for failed in failed_files[:10]:  # Show first 10 failures
                logger.warning(f"  - {failed}")

        return downloaded_files

    def _download_file(self, spec: GribFileSpec) -> tuple[bool, str]:
        """
        Download a single GRIB file.

        Args:
            spec: File specification

        Returns:
            Tuple of (success, destination_path)
        """
        # Parse source and destination paths
        source_bucket, source_blob = parse_gcs_path(spec.source_path)
        dest_bucket, dest_blob = parse_gcs_path(spec.destination_path)

        # Check if destination already exists
        if not self.config.overwrite:
            if gcs_blob_exists(dest_bucket, dest_blob, self.client):
                logger.debug(f"Skipping existing file: {spec.destination_path}")
                return True, spec.destination_path

        # Check if source exists
        if not gcs_blob_exists(source_bucket, source_blob, self.client):
            logger.warning(f"Source file not found: {spec.source_path}")
            return False, spec.destination_path

        # Copy the file
        success = copy_gcs_blob(
            source_bucket=source_bucket,
            source_blob=source_blob,
            dest_bucket=dest_bucket,
            dest_blob=dest_blob,
            client=self.client,
        )

        if success:
            logger.debug(f"Downloaded: {spec.destination_path}")
        else:
            logger.error(f"Failed to download: {spec.source_path}")

        return success, spec.destination_path

    def get_download_manifest(self) -> List[dict]:
        """
        Get manifest of files to be downloaded without actually downloading.

        Returns:
            List of file specifications as dictionaries
        """
        file_specs = self.data_source.get_file_list()
        return [
            {
                "source_path": spec.source_path,
                "destination_path": spec.destination_path,
                "lead_time": spec.lead_time,
                "forecast_time": spec.forecast_time.isoformat(),
            }
            for spec in file_specs
        ]

    def verify_downloads(self, file_paths: List[str]) -> dict:
        """
        Verify that downloaded files exist and are accessible.

        Args:
            file_paths: List of file paths to verify

        Returns:
            Dictionary with verification results
        """
        results = {"total": len(file_paths), "exists": 0, "missing": []}

        for path in file_paths:
            bucket, blob = parse_gcs_path(path)
            if gcs_blob_exists(bucket, blob, self.client):
                results["exists"] += 1
            else:
                results["missing"].append(path)

        return results
