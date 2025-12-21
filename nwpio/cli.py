"""Command-line interface for NWP download."""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from nwpio import GribDownloader, GribProcessor
from nwpio.config import DownloadConfig, ProcessConfig, WorkflowConfig

# Default logging configuration (can be overridden by --log-level)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def set_log_level(level: str) -> None:
    """Set logging level for all nwpio loggers."""
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")
    
    # Set root logger level
    logging.getLogger().setLevel(numeric_level)
    # Set nwpio package logger level
    logging.getLogger("nwpio").setLevel(numeric_level)


@click.group()
@click.version_option(version="0.1.0")
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    envvar="LOG_LEVEL",
    help="Set logging level. Reads from $LOG_LEVEL if not provided.",
)
@click.pass_context
def main(ctx, log_level: str):
    """NWPIO - Download and process NWP forecast data."""
    set_log_level(log_level)
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level


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
    "--no-clean-coords",
    is_flag=True,
    help="Skip cleaning coordinates (keep all GRIB metadata coordinates)",
)
@click.option(
    "--rename-vars",
    type=str,
    default=None,
    help='Rename variables as JSON string (e.g., \'{"u10": "u", "v10": "v"}\')',
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
    no_clean_coords: bool,
    rename_vars: Optional[str],
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
        rename_dict = json.loads(rename_vars) if rename_vars else None

        # Create configuration
        config = ProcessConfig(
            grib_path=grib_path,
            variables=variable_list,
            zarr_path=output,
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
            clean_coords=not no_clean_coords,
            rename_vars=rename_dict,
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
            zarr_path = processor.process()
            click.echo(f"\nSuccessfully created Zarr archive: {zarr_path}")

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        sys.exit(1)


@main.command()
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    envvar="CONFIG",
    help="Path to YAML configuration file. Reads from $CONFIG if not provided.",
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
    "--process-task",
    type=str,
    multiple=True,
    help="Process only specific task(s) by name. Can be specified multiple times. If not provided, runs all tasks.",
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
    process_task: tuple,
    max_workers: int,
):
    """Run complete workflow from configuration file."""
    try:
        # Validate config is provided
        if config is None:
            raise click.ClickException(
                "Config file not specified. Provide via --config argument or $CONFIG environment variable."
            )

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
        logger.info(
            f"Product: {workflow_config.download.product} {workflow_config.download.resolution}"
        )
        logger.info(f"Max lead time: {workflow_config.download.max_lead_time}h")
        logger.info(
            f"Source: {workflow_config.download.source_type.upper()} (bucket: {workflow_config.download.source_bucket})"
        )

        downloaded_files = []

        # Download step
        if not skip_download:
            click.echo("=== Download Step ===")
            downloader = GribDownloader(
                workflow_config.download, max_workers=max_workers
            )

            # Clean destination files if requested
            if workflow_config.download.clean_destination:
                click.echo("Cleaning existing destination files...")
                deleted = downloader.clean_destination_files()
                click.echo(f"Deleted {deleted} existing files")

            # Validate file availability before downloading
            if workflow_config.download.validate_before_download:
                click.echo("Validating file availability...")
                downloader.validate_availability()  # Raises FileNotFoundError if missing

            downloaded_files = downloader.download()
            click.echo(f"Downloaded {len(downloaded_files)} files\n")

        # Process step(s) - can run multiple processes on the same downloaded files
        if skip_process:
            click.echo("Skipping process step (--skip-process flag)\n")
        elif not workflow_config.process:
            click.echo("No process configuration found - download only\n")
        elif workflow_config.process:
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

            # Determine which tasks to run
            all_tasks = workflow_config.process
            if process_task:
                # Validate requested tasks exist
                invalid_tasks = set(process_task) - set(all_tasks.keys())
                if invalid_tasks:
                    available = ", ".join(all_tasks.keys())
                    raise click.ClickException(
                        f"Unknown process task(s): {', '.join(invalid_tasks)}. "
                        f"Available tasks: {available}"
                    )
                tasks_to_run = {k: all_tasks[k] for k in process_task}
            else:
                tasks_to_run = all_tasks

            zarr_paths = []
            for idx, (task_name, process_config) in enumerate(tasks_to_run.items(), 1):
                click.echo(f"=== Process Step {idx}/{len(tasks_to_run)}: {task_name} ===")

                # Set grib_path if not provided
                if not process_config.grib_path:
                    if grib_dir:
                        # Use directory from downloaded files
                        process_config.grib_path = grib_dir
                    else:
                        # Derive from download config
                        process_config.grib_path = (
                            workflow_config.get_default_grib_path()
                        )
                        click.echo(
                            f"Using default grib_path: {process_config.grib_path}"
                        )
                elif grib_dir:
                    # Override explicit grib_path if we downloaded files
                    process_config.grib_path = grib_dir

                # Pass cycle from download config for path formatting
                processor = GribProcessor(
                    process_config, cycle=workflow_config.download.cycle
                )
                zarr_path = processor.process()
                zarr_paths.append(zarr_path)
                click.echo(f"Created Zarr archive: {zarr_path}\n")

            click.echo(f"Created {len(zarr_paths)} Zarr archives")

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
        process={
            "surface": ProcessConfig(
                grib_path="gs://your-bucket-name/nwp-data/",
                variables=["t2m", "u10", "v10", "tp"],
                zarr_path="gs://your-bucket-name/output.zarr",
            ),
        },
        cleanup_grib=False,
    )

    # Save to file
    config.to_yaml(output)
    click.echo(f"Created sample configuration file: {output}")
    click.echo("\nEdit this file with your specific settings and run:")
    click.echo(f"  nwpio run --config {output}")


if __name__ == "__main__":
    main()
