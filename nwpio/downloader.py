"""GRIB file downloader from cloud archives."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from tqdm import tqdm

from nwpio.config import DownloadConfig
from nwpio.sources import GribFileSpec, create_data_source
from nwpio.utils import (
    copy_gcs_blob,
    gcs_blob_exists,
    get_gcs_client,
    parse_gcs_path,
)


def parse_cloud_path(path: str) -> tuple[str, str, str]:
    """Parse cloud storage path (GCS or S3) into protocol, bucket, and blob.

    Args:
        path: Cloud path (gs://bucket/path or s3://bucket/path)

    Returns:
        Tuple of (protocol, bucket, blob_path)
    """
    if path.startswith("gs://"):
        bucket, blob = parse_gcs_path(path)
        return "gs", bucket, blob
    elif path.startswith("s3://"):
        path = path.replace("s3://", "")
        parts = path.split("/", 1)
        bucket = parts[0]
        blob = parts[1] if len(parts) > 1 else ""
        return "s3", bucket, blob
    else:
        raise ValueError(f"Unsupported path protocol: {path}")


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
            local_download_dir=config.local_download_dir,
            source_type=config.source_type,
        )

    def validate_availability(self) -> None:
        """
        Validate that all required files are available in the source bucket.
        Also checks that the next lead time file exists to ensure the last
        required file is fully uploaded.

        Raises:
            FileNotFoundError: If any required files are missing, with detailed
                             information about which files are missing and available
        """
        import fsspec
        from datetime import timedelta

        file_specs = self.data_source.get_file_list()
        next_lead_time = self.data_source.get_next_lead_time()

        # Build the next file spec for validation
        validation_specs = list(file_specs)
        if next_lead_time is not None:
            # Generate the next file path using the same pattern
            if self.config.product == "gfs":
                cycle_str = f"{self.config.cycle.hour:02d}"
                date_str = self.config.cycle.strftime("%Y%m%d")
                lead_str = f"{next_lead_time:03d}"
                next_source_path = (
                    f"gs://{self.config.source_bucket}/gfs.{date_str}/{cycle_str}/atmos/"
                    f"gfs.t{cycle_str}z.pgrb2.{self.config.resolution}.f{lead_str}"
                )
            else:
                # ECMWF pattern
                cycle_str = f"{self.config.cycle.hour:02d}"
                date_str = self.config.cycle.strftime("%Y%m%d")
                lead_str = f"{next_lead_time:03d}"
                product_type = "ens" if "ens" in self.config.product else "hres"
                
                # Determine source type
                source_type = self.config.source_type
                if not source_type:
                    # Infer from bucket name
                    if self.config.source_bucket == "ecmwf-forecasts":
                        source_type = "aws"
                    elif self.config.source_bucket == "ecmwf-open-data":
                        source_type = "gcs"
                    else:
                        source_type = "gcs"  # Default

                if "ens" in self.config.product:
                    product_name = "enfo"
                    product_suffix = "ef"
                else:
                    product_name = "oper"
                    product_suffix = "fc"

                if source_type == "aws":
                    next_source_path = (
                        f"s3://{self.config.source_bucket}/{date_str}/{cycle_str}z/ifs/{self.config.resolution}/{product_name}/"
                        f"{date_str}{cycle_str}0000-{next_lead_time}h-{product_name}-{product_suffix}.grib2"
                    )
                else:
                    # GCS official bucket pattern
                    next_source_path = (
                        f"gs://{self.config.source_bucket}/{date_str}/{cycle_str}z/ifs/{self.config.resolution}/{product_name}/"
                        f"{date_str}{cycle_str}0000-{next_lead_time}h-{product_name}-{product_suffix}.grib2"
                    )

            from nwpio.sources import GribFileSpec

            next_spec = GribFileSpec(
                source_path=next_source_path,
                destination_path="",  # Not needed for validation
                lead_time=next_lead_time,
                forecast_time=self.config.cycle + timedelta(hours=next_lead_time),
            )
            validation_specs.append(next_spec)

        # Check which files exist
        # Determine filesystem type from first file
        first_path = file_specs[0].source_path if file_specs else ""
        if first_path.startswith("s3://"):
            fs = fsspec.filesystem(
                "s3", anon=True
            )  # Anonymous access for public buckets
        else:
            fs = fsspec.filesystem("gs")

        missing_files = []
        available_files = []

        for spec in validation_specs:
            protocol, bucket_name, blob_path = parse_cloud_path(spec.source_path)
            cloud_path = f"{bucket_name}/{blob_path}"

            if not fs.exists(cloud_path):
                missing_files.append(spec)
            else:
                available_files.append(spec)

        if missing_files:
            # Separate required vs validation file
            required_missing = [
                s for s in missing_files if s.lead_time <= self.config.max_lead_time
            ]
            validation_missing = [
                s for s in missing_files if s.lead_time > self.config.max_lead_time
            ]

            # Build detailed error message
            error_lines = [
                f"\n{'=' * 80}",
                "GRIB FILES NOT READY - Forecast cycle incomplete",
                f"{'=' * 80}",
                f"Product: {self.config.product}",
                f"Cycle: {self.config.cycle.strftime('%Y-%m-%d %H:%M:%S')} UTC",
                f"Resolution: {self.config.resolution}",
                f"Requested lead time: 0-{self.config.max_lead_time}h",
                "",
                "Status:",
                f"  ✓ Available: {len(available_files)} files",
                f"  ✗ Missing: {len(missing_files)} files",
                "",
            ]

            if required_missing:
                # Get lead times
                missing_lead_times = sorted([s.lead_time for s in required_missing])
                available_lead_times = sorted(
                    [
                        s.lead_time
                        for s in available_files
                        if s.lead_time <= self.config.max_lead_time
                    ]
                )

                error_lines.extend(
                    [
                        f"Missing required lead times ({len(missing_lead_times)}):",
                        f"  {missing_lead_times[:20]}{'...' if len(missing_lead_times) > 20 else ''}",
                        "",
                        f"Available lead times ({len(available_lead_times)}):",
                        f"  {available_lead_times[:20]}{'...' if len(available_lead_times) > 20 else ''}",
                        "",
                    ]
                )

            if validation_missing:
                error_lines.extend(
                    [
                        "Validation file missing:",
                        f"  Lead time {next_lead_time}h not yet available",
                        f"  (This ensures lead time {self.config.max_lead_time}h is fully uploaded)",
                        "",
                    ]
                )

            error_lines.extend(
                [
                    "Action:",
                    "  The forecast cycle is still processing. This task will be retried.",
                    "  Typical GFS processing time: 3-4 hours after cycle start",
                    f"{'=' * 80}",
                ]
            )

            error_msg = "\n".join(error_lines)
            logger.error(error_msg)

            raise FileNotFoundError(
                f"Missing {len(missing_files)} GRIB files for cycle "
                f"{self.config.cycle.strftime('%Y%m%d_%Hz')}. "
                f"Forecast not yet complete. See logs for details."
            )

        logger.info(
            f"✓ All {len(file_specs)} required files available "
            f"(validated with lead time {next_lead_time}h)"
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
                executor.submit(self._download_file, spec): spec for spec in file_specs
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
        # Check if downloading to local or GCS
        if spec.destination_path.startswith("gs://"):
            # Cloud to GCS copy
            source_protocol, source_bucket, source_blob = parse_cloud_path(
                spec.source_path
            )
            dest_bucket, dest_blob = parse_gcs_path(spec.destination_path)

            # Check if destination already exists
            if not self.config.overwrite:
                if gcs_blob_exists(dest_bucket, dest_blob, self.client):
                    logger.debug(f"Skipping existing file: {spec.destination_path}")
                    return True, spec.destination_path

            if source_protocol == "gs":
                # GCS to GCS copy
                if not gcs_blob_exists(source_bucket, source_blob, self.client):
                    logger.warning(f"Source file not found: {spec.source_path}")
                    return False, spec.destination_path

                success = copy_gcs_blob(
                    source_bucket=source_bucket,
                    source_blob=source_blob,
                    dest_bucket=dest_bucket,
                    dest_blob=dest_blob,
                    client=self.client,
                )
            else:
                # S3 to GCS copy
                import fsspec

                try:
                    s3_fs = fsspec.filesystem("s3", anon=True)
                    s3_path = f"{source_bucket}/{source_blob}"

                    with s3_fs.open(s3_path, "rb") as src:
                        data = src.read()

                    # Upload to GCS
                    dest_bucket_obj = self.client.bucket(dest_bucket)
                    blob = dest_bucket_obj.blob(dest_blob)
                    blob.upload_from_string(data)
                    success = True
                except Exception as e:
                    logger.error(f"Failed to copy {spec.source_path} to GCS: {e}")
                    success = False
        else:
            # Cloud to local download
            from pathlib import Path
            import fsspec

            local_path = Path(spec.destination_path)

            # Check if destination already exists
            if not self.config.overwrite and local_path.exists():
                logger.debug(f"Skipping existing file: {spec.destination_path}")
                return True, spec.destination_path

            # Create parent directory
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Download from cloud storage
            try:
                source_protocol, source_bucket, source_blob = parse_cloud_path(
                    spec.source_path
                )

                if source_protocol == "gs":
                    fs = fsspec.filesystem("gs")
                else:  # s3
                    fs = fsspec.filesystem("s3", anon=True)

                cloud_path = f"{source_bucket}/{source_blob}"

                with fs.open(cloud_path, "rb") as src:
                    with open(local_path, "wb") as dst:
                        dst.write(src.read())

                success = True
            except Exception as e:
                logger.error(f"Failed to download {spec.source_path}: {e}")
                success = False

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
