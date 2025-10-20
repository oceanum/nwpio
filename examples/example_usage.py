"""Example usage of NWP Download library."""

from datetime import datetime
from nwpio import GribDownloader, GribProcessor, DownloadConfig, ProcessConfig


def example_download():
    """Example: Download GFS GRIB files."""
    config = DownloadConfig(
        product="gfs",
        resolution="0p25",
        forecast_time=datetime(2024, 1, 1, 0),
        cycle="00z",
        max_lead_time=120,
        source_bucket="gcp-public-data-arco-era5",
        destination_bucket="your-bucket-name",
        destination_prefix="nwp-data/",
        overwrite=False,
    )

    downloader = GribDownloader(config, max_workers=10)

    # Preview what will be downloaded
    manifest = downloader.get_download_manifest()
    print(f"Will download {len(manifest)} files")

    # Perform download
    downloaded_files = downloader.download()
    print(f"Downloaded {len(downloaded_files)} files")

    # Verify downloads
    verification = downloader.verify_downloads(downloaded_files)
    print(f"Verified {verification['exists']}/{verification['total']} files")

    return downloaded_files


def example_process():
    """Example: Process GRIB files to Zarr."""
    config = ProcessConfig(
        grib_path="gs://your-bucket-name/nwp-data/gfs/0p25/20240101/00/",
        variables=["t2m", "u10", "v10", "tp"],
        zarr_path="gs://your-bucket-name/output/forecast.zarr",
        chunks={"time": 1, "latitude": 100, "longitude": 100},
        compression="default",
        overwrite=False,
    )

    processor = GribProcessor(config)

    # Inspect GRIB files first
    metadata = processor.inspect_grib_files()
    print(f"Found {metadata['num_files']} GRIB files")
    print(f"Available variables: {metadata['variables']}")

    # Process to Zarr
    zarr_path = processor.process()
    print(f"Created Zarr archive: {zarr_path}")


def example_ecmwf():
    """Example: Download ECMWF HRES data."""
    config = DownloadConfig(
        product="ecmwf-hres",
        resolution="0p1",
        forecast_time=datetime(2024, 1, 1, 0),
        cycle="00z",
        max_lead_time=240,
        source_bucket="ecmwf-public-data",
        destination_bucket="your-bucket-name",
        destination_prefix="ecmwf-data/",
    )

    downloader = GribDownloader(config)
    downloaded_files = downloader.download()
    print(f"Downloaded {len(downloaded_files)} ECMWF files")


def example_with_filters():
    """Example: Process GRIB with specific filters."""
    config = ProcessConfig(
        grib_path="gs://your-bucket-name/nwp-data/",
        variables=["t", "u", "v"],  # Temperature and wind at pressure levels
        zarr_path="gs://your-bucket-name/output/pressure_levels.zarr",
        filter_by_keys={
            "typeOfLevel": "isobaricInhPa",
            "level": 500,  # 500 hPa level
        },
        chunks={"time": 1, "latitude": 50, "longitude": 50},
    )

    processor = GribProcessor(config)
    zarr_path = processor.process()
    print(f"Created pressure level Zarr: {zarr_path}")


if __name__ == "__main__":
    print("=== Example 1: Download GFS data ===")
    # example_download()

    print("\n=== Example 2: Process GRIB to Zarr ===")
    # example_process()

    print("\n=== Example 3: Download ECMWF data ===")
    # example_ecmwf()

    print("\n=== Example 4: Process with filters ===")
    # example_with_filters()

    print("\nUncomment the function calls to run the examples")
