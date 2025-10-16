"""Command-line interface for NWP download."""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from nwp_download import GribDownloader, GribProcessor
from nwp_download.config import DownloadConfig, ProcessConfig, WorkflowConfig

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
    """NWP Download - Download and process NWP forecast data."""
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
    "--time",
    type=str,
    required=True,
    help="Forecast initialization time (ISO format: YYYY-MM-DDTHH:MM:SS)",
)
@click.option(
    "--cycle",
    type=click.Choice(["00z", "06z", "12z", "18z"]),
    required=True,
    help="Forecast cycle",
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
    time: str,
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
        # Parse forecast time
        forecast_time = datetime.fromisoformat(time)

        # Create configuration
        config = DownloadConfig(
            product=product,
            resolution=resolution,
            forecast_time=forecast_time,
            cycle=cycle,
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
            click.echo(f"Verification: {verification['exists']}/{verification['total']} files exist")

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
    help="GRIB filter keys as JSON string (e.g., '{\"typeOfLevel\": \"surface\"}')",
)
@click.option(
    "--chunks",
    type=str,
    default=None,
    help="Chunking specification as JSON string (e.g., '{\"time\": 1, \"latitude\": 100}')",
)
@click.option(
    "--compression",
    type=click.Choice(["default", "zstd", "lz4", "none"]),
    default="default",
    help="Compression algorithm for Zarr",
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Overwrite existing Zarr archive",
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
    compression: str,
    overwrite: bool,
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
            compression=compression,
            overwrite=overwrite,
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
    skip_download: bool,
    skip_process: bool,
    max_workers: int,
):
    """Run complete workflow from configuration file."""
    try:
        # Load configuration
        workflow_config = WorkflowConfig.from_yaml(config)

        downloaded_files = []

        # Download step
        if not skip_download:
            click.echo("=== Download Step ===")
            downloader = GribDownloader(workflow_config.download, max_workers=max_workers)
            downloaded_files = downloader.download()
            click.echo(f"Downloaded {len(downloaded_files)} files\n")

        # Process step
        if not skip_process:
            click.echo("=== Process Step ===")
            processor = GribProcessor(workflow_config.process)
            output_path = processor.process()
            click.echo(f"Created Zarr archive: {output_path}\n")

        # Cleanup step
        if workflow_config.cleanup_grib and downloaded_files:
            click.echo("=== Cleanup Step ===")
            # TODO: Implement cleanup logic
            click.echo("Cleanup not yet implemented")

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
            forecast_time=datetime(2024, 1, 1, 0),
            cycle="00z",
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
    click.echo(f"  nwp-download run --config {output}")


if __name__ == "__main__":
    main()
