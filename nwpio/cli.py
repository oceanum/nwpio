"""Command-line interface for NWP download."""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from nwpio import GribDownloader, GribProcessor
from nwpio.config import DownloadConfig, ProcessConfig, WorkflowConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="0.1.0")
def main():
    """NWPIO - Download and process NWP forecast data."""
    pass


@main.command()
@click.option(
    "--product",
    type=click.Choice(["gfs", "ecmwf-hres", "ecmwf-ens"]),
    required=True,
    help="NWP product to download",
)
@click.option(
    "--resolution",
    type=str,
    required=True,
    help="Model resolution (e.g., 0p25 for 0.25 degrees)",
)
@click.option(
    "--cycle",
    type=str,
    required=True,
    help="Forecast initialization time/cycle (ISO format: YYYY-MM-DDTHH:MM:SS, hour must be 0, 6, 12, or 18)",
)
@click.option(
    "--max-lead-time",
    type=int,
    required=True,
    help="Maximum lead time in hours",
)
@click.option(
    "--source-bucket",
    type=str,
    required=True,
    help="Source GCS bucket containing GRIB files",
)
@click.option(
    "--dest-bucket",
    type=str,
    required=True,
    help="Destination GCS bucket for downloaded files",
)
@click.option(
    "--dest-prefix",
    type=str,
    default="",
    help="Optional prefix for destination paths",
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Overwrite existing files",
)
@click.option(
    "--max-workers",
    type=int,
    default=10,
    help="Maximum number of parallel download workers",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be downloaded without actually downloading",
)
def download(
    product: str,
    resolution: str,
    cycle: str,
    max_lead_time: int,
    source_bucket: str,
    dest_bucket: str,
    dest_prefix: str,
    overwrite: bool,
    max_workers: int,
    dry_run: bool,
):
    """Download GRIB files from cloud archives."""
    try:
        # Parse cycle time
        cycle_time = datetime.fromisoformat(cycle)

        # Create configuration
        config = DownloadConfig(
            product=product,
            resolution=resolution,
            cycle=cycle_time,
            max_lead_time=max_lead_time,
            source_bucket=source_bucket,
            destination_bucket=dest_bucket,
            destination_prefix=dest_prefix,
            overwrite=overwrite,
        )

        # Create downloader
        downloader = GribDownloader(config, max_workers=max_workers)

        if dry_run:
            # Show manifest without downloading
            manifest = downloader.get_download_manifest()
            click.echo(f"\nWould download {len(manifest)} files:")
            for item in manifest[:10]:  # Show first 10
                click.echo(f"  {item['source_path']} -> {item['destination_path']}")
            if len(manifest) > 10:
                click.echo(f"  ... and {len(manifest) - 10} more files")
        else:
            # Perform download
            downloaded_files = downloader.download()
            click.echo(f"\nSuccessfully downloaded {len(downloaded_files)} files")

            # Verify downloads
            verification = downloader.verify_downloads(downloaded_files)
            click.echo(
                f"Verification: {verification['exists']}/{verification['total']} files exist"
            )

    except Exception as e:
        logger.error(f"Download failed: {e}")
        sys.exit(1)


@main.command()
@click.option(
    "--grib-path",
    type=str,
    required=True,
    help="Path to GRIB files (local or GCS)",
)
@click.option(
    "--variables",
    type=str,
    required=True,
    help="Comma-separated list of variables to extract",
)
@click.option(
    "--output",
    type=str,
    required=True,
    help="Output path for Zarr archive (local or GCS)",
)
@click.option(
    "--filter-keys",
    type=str,
    default=None,
    help='GRIB filter keys as JSON string (e.g., \'{"typeOfLevel": "surface"}\')',
)
@click.option(
    "--chunks",
    type=str,
    default=None,
    help='Chunking specification as JSON string (e.g., \'{"time": 1, "latitude": 100}\')',
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Overwrite existing Zarr archive",
)
@click.option(
    "--write-local-first",
    is_flag=True,
    help="Write to local temp directory first, then upload to GCS (helps with network issues)",
)
@click.option(
    "--local-temp-dir",
    type=str,
    default=None,
    help="Local temporary directory for write-local-first",
)
@click.option(
    "--max-upload-workers",
    type=int,
    default=16,
    help="Maximum number of parallel workers for uploading to GCS",
)
@click.option(
    "--upload-timeout",
    type=int,
    default=600,
    help="Timeout in seconds for individual file uploads to GCS",
)
@click.option(
    "--upload-max-retries",
    type=int,
    default=3,
    help="Maximum number of retries for failed uploads",
)
@click.option(
    "--no-verify-upload",
    is_flag=True,
    help="Skip upload verification (not recommended)",
)
@click.option(
    "--max-grib-workers",
    type=int,
    default=4,
    help="Maximum number of parallel workers for loading GRIB files",
)
@click.option(
    "--inspect",
    is_flag=True,
    help="Inspect GRIB files without processing",
)
def process(
    grib_path: str,
    variables: str,
    output: str,
    filter_keys: Optional[str],
    chunks: Optional[str],
    overwrite: bool,
    write_local_first: bool,
    local_temp_dir: Optional[str],
    max_upload_workers: int,
    upload_timeout: int,
    upload_max_retries: int,
    no_verify_upload: bool,
    max_grib_workers: int,
    inspect: bool,
):
    """Process GRIB files and convert to Zarr."""
    try:
        import json

        # Parse variables
        variable_list = [v.strip() for v in variables.split(",")]

        # Parse optional JSON parameters
        filter_dict = json.loads(filter_keys) if filter_keys else None
        chunks_dict = json.loads(chunks) if chunks else None

        # Create configuration
        config = ProcessConfig(
            grib_path=grib_path,
            variables=variable_list,
            output_path=output,
            filter_by_keys=filter_dict,
            chunks=chunks_dict,
            overwrite=overwrite,
            write_local_first=write_local_first,
            local_temp_dir=local_temp_dir,
            max_upload_workers=max_upload_workers,
            upload_timeout=upload_timeout,
            upload_max_retries=upload_max_retries,
            verify_upload=not no_verify_upload,
            max_grib_workers=max_grib_workers,
        )

        # Create processor
        processor = GribProcessor(config)

        if inspect:
            # Inspect GRIB files
            metadata = processor.inspect_grib_files()
            click.echo("\nGRIB File Metadata:")
            click.echo(f"  Number of files: {metadata.get('num_files', 'N/A')}")
            click.echo(f"  Variables: {', '.join(metadata.get('variables', []))}")
            click.echo(f"  Dimensions: {metadata.get('dimensions', {})}")
            click.echo(f"  Sample file: {metadata.get('sample_file', 'N/A')}")
        else:
            # Process GRIB files
            output_path = processor.process()
            click.echo(f"\nSuccessfully created Zarr archive: {output_path}")

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        sys.exit(1)


@main.command()
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to YAML configuration file",
)
@click.option(
    "--cycle",
    type=str,
    envvar="CYCLE",
    help="Forecast cycle (ISO format: YYYY-MM-DDTHH:MM:SS). Reads from $CYCLE if not provided. Overrides config file.",
)
@click.option(
    "--skip-download",
    is_flag=True,
    help="Skip download step",
)
@click.option(
    "--skip-process",
    is_flag=True,
    help="Skip process step",
)
@click.option(
    "--max-workers",
    type=int,
    default=10,
    help="Maximum number of parallel download workers",
)
def run(
    config: Path,
    cycle: str,
    skip_download: bool,
    skip_process: bool,
    max_workers: int,
):
    """Run complete workflow from configuration file."""
    try:
        # Load configuration
        workflow_config = WorkflowConfig.from_yaml(config)
        
        # Set cycle from CLI/env or validate it's in config
        if cycle:
            from datetime import datetime
            workflow_config.download.cycle = datetime.fromisoformat(cycle)
        elif workflow_config.download.cycle is None:
            raise click.ClickException(
                "Cycle not specified. Provide via --cycle argument, $CYCLE environment variable, or in config file."
            )

        # Log workflow information
        logger.info(f"Starting workflow for cycle: {workflow_config.download.cycle}")
        logger.info(f"Product: {workflow_config.download.product} {workflow_config.download.resolution}")
        logger.info(f"Max lead time: {workflow_config.download.max_lead_time}h")

        downloaded_files = []

        # Download step
        if not skip_download:
            click.echo("=== Download Step ===")
            downloader = GribDownloader(
                workflow_config.download, max_workers=max_workers
            )

            # Validate file availability before downloading
            if workflow_config.download.validate_before_download:
                click.echo("Validating file availability...")
                downloader.validate_availability()  # Raises FileNotFoundError if missing

            downloaded_files = downloader.download()
            click.echo(f"Downloaded {len(downloaded_files)} files\n")

        # Process step(s) - can run multiple processes on the same downloaded files
        if not skip_process:
            # Determine GRIB path from downloaded files or config
            if downloaded_files:
                # Use the directory of downloaded files
                from pathlib import Path

                first_file = downloaded_files[0]
                if first_file.startswith("gs://"):
                    # For GCS paths, extract directory manually
                    grib_dir = "/".join(first_file.split("/")[:-1]) + "/"
                else:
                    # For local paths, use Path
                    grib_dir = str(Path(first_file).parent)
                click.echo(f"Processing GRIB files from: {grib_dir}\n")
            else:
                grib_dir = None

            output_paths = []
            for idx, process_config in enumerate(workflow_config.process, 1):
                click.echo(f"=== Process Step {idx}/{len(workflow_config.process)} ===")

                # Override grib_path if we downloaded files
                if grib_dir:
                    process_config.grib_path = grib_dir

                # Pass cycle from download config for path formatting
                processor = GribProcessor(
                    process_config, cycle=workflow_config.download.cycle
                )
                output_path = processor.process()
                output_paths.append(output_path)
                click.echo(f"Created Zarr archive: {output_path}\n")

            click.echo(f"Created {len(output_paths)} Zarr archives")

        # Cleanup step
        if workflow_config.cleanup_grib and downloaded_files:
            click.echo("=== Cleanup Step ===")
            import os

            for file_path in downloaded_files:
                try:
                    os.remove(file_path)
                    logger.info(f"Deleted {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete {file_path}: {e}")
            click.echo(f"Cleaned up {len(downloaded_files)} GRIB files")

        click.echo("=== Workflow Complete ===")

    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        sys.exit(1)


@main.command()
@click.option(
    "--product",
    type=click.Choice(["gfs", "ecmwf-hres", "ecmwf-ens"]),
    default="gfs",
    help="NWP product",
)
@click.option(
    "--resolution",
    type=str,
    default="0p25",
    help="Model resolution",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=Path("config.yaml"),
    help="Output configuration file path",
)
def init_config(product: str, resolution: str, output: Path):
    """Generate a sample configuration file."""
    from datetime import datetime

    # Create sample configuration
    config = WorkflowConfig(
        download=DownloadConfig(
            product=product,
            resolution=resolution,
            cycle=datetime(2024, 1, 1, 0),
            max_lead_time=120,
            source_bucket="gcp-public-data-arco-era5",
            destination_bucket="your-bucket-name",
            destination_prefix="nwp-data/",
        ),
        process=ProcessConfig(
            grib_path="gs://your-bucket-name/nwp-data/",
            variables=["t2m", "u10", "v10", "tp"],
            output_path="gs://your-bucket-name/output.zarr",
        ),
        cleanup_grib=False,
    )

    # Save to file
    config.to_yaml(output)
    click.echo(f"Created sample configuration file: {output}")
    click.echo("\nEdit this file with your specific settings and run:")
    click.echo(f"  nwpio run --config {output}")


if __name__ == "__main__":
    main()
