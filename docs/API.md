# API Reference

## Configuration Models

### DownloadConfig

Configuration for downloading GRIB files from cloud archives.

```python
from nwp_download import DownloadConfig
from datetime import datetime

config = DownloadConfig(
    product="gfs",                              # Product: gfs, ecmwf-hres, ecmwf-ens
    resolution="0p25",                          # Resolution: 0p25, 0p50, 1p00, etc.
    forecast_time=datetime(2024, 1, 1, 0),     # Forecast initialization time
    cycle="00z",                                # Cycle: 00z, 06z, 12z, 18z
    max_lead_time=120,                          # Maximum lead time in hours
    source_bucket="gcp-public-data-arco-era5", # Source GCS bucket
    destination_bucket="your-bucket-name",      # Destination GCS bucket
    destination_prefix="nwp-data/",             # Optional path prefix
    overwrite=False,                            # Overwrite existing files
)
```

**Fields:**

- `product` (str): NWP product to download. Options: "gfs", "ecmwf-hres", "ecmwf-ens"
- `resolution` (str): Model resolution (e.g., "0p25" for 0.25 degrees)
- `forecast_time` (datetime): Forecast initialization time
- `cycle` (str): Forecast cycle. Options: "00z", "06z", "12z", "18z"
- `max_lead_time` (int): Maximum lead time in hours (must be > 0)
- `source_bucket` (str): Source GCS bucket containing GRIB files
- `destination_bucket` (str): Destination GCS bucket for downloaded files
- `destination_prefix` (str, optional): Prefix for destination paths
- `overwrite` (bool): Whether to overwrite existing files (default: False)

**Validation:**

- ECMWF products only support 00z and 12z cycles
- GFS max lead time: 384 hours
- ECMWF HRES max lead time: 240 hours
- ECMWF ENS max lead time: 360 hours

### ProcessConfig

Configuration for processing GRIB files to Zarr format.

```python
from nwp_download import ProcessConfig

config = ProcessConfig(
    grib_path="gs://bucket/path/to/grib/",     # Path to GRIB files
    variables=["t2m", "u10", "v10", "tp"],     # Variables to extract
    output_path="gs://bucket/output.zarr",      # Output Zarr path
    filter_by_keys={"typeOfLevel": "surface"},  # Optional GRIB filters
    chunks={"time": 1, "latitude": 100},        # Optional chunking
    compression="default",                      # Compression algorithm
    overwrite=False,                            # Overwrite existing Zarr
)
```

**Fields:**

- `grib_path` (str): Path to GRIB files (local or GCS)
- `variables` (List[str]): List of variables to extract from GRIB files
- `output_path` (str): Output path for Zarr archive (local or GCS). Supports placeholders:
  - `{timestamp}`: Formatted timestamp (uses `timestamp_format`)
  - `{date}`: Date in YYYYMMDD format
  - `{time}`: Time in HHMMSS format
  - `{cycle}`: Forecast cycle (e.g., "00z", "12z")
- `filter_by_keys` (dict, optional): Additional GRIB key filters
- `chunks` (dict, optional): Chunking specification for Zarr
- `overwrite` (bool): Whether to overwrite existing Zarr archive (default: False)
- `timestamp_format` (str): Format string for `{timestamp}` placeholder (default: "%Y%m%d_%H%M%S")
- `write_local_first` (bool): Write to local temp directory first, then upload to GCS (default: False)
- `local_temp_dir` (str, optional): Local temporary directory for write_local_first (default: system temp dir)

**Timestamp Examples:**

```python
# Using date and cycle
ProcessConfig(
    output_path="gs://bucket/forecast_{date}_{cycle}.zarr",
    # Results in: forecast_20240101_00z.zarr
)

# Using custom timestamp
ProcessConfig(
    output_path="gs://bucket/forecast_{timestamp}.zarr",
    timestamp_format="%Y-%m-%d_%H%M",
    # Results in: forecast_2024-01-01_0000.zarr
)

# Multiple cycles in same directory
ProcessConfig(
    output_path="gs://bucket/forecasts/gfs_{date}_{cycle}.zarr",
    # Results in: forecasts/gfs_20240101_00z.zarr, gfs_20240101_06z.zarr, etc.
)

# Write locally first to avoid network issues
ProcessConfig(
    output_path="gs://bucket/forecast_{date}_{cycle}.zarr",
    write_local_first=True,  # Write to temp dir, then upload
    local_temp_dir="/tmp/zarr-staging",  # Optional custom temp dir
)
```

### WorkflowConfig

Combined configuration for download and process workflow.

```python
from nwp_download import WorkflowConfig, DownloadConfig, ProcessConfig
from pathlib import Path

# Create from components
config = WorkflowConfig(
    download=DownloadConfig(...),
    process=ProcessConfig(...),
    cleanup_grib=False,
)

# Load from YAML
config = WorkflowConfig.from_yaml(Path("config.yaml"))

# Save to YAML
config.to_yaml(Path("config.yaml"))
```

**Fields:**

- `download` (DownloadConfig): Download configuration
- `process` (ProcessConfig): Process configuration
- `cleanup_grib` (bool): Delete GRIB files after processing (default: False)

## Core Classes

### GribDownloader

Download GRIB files from cloud archives to GCS.

```python
from nwp_download import GribDownloader, DownloadConfig

downloader = GribDownloader(
    config=DownloadConfig(...),
    max_workers=10,  # Number of parallel workers
)
```

**Methods:**

#### download()

Download all GRIB files for the configured forecast.

```python
downloaded_files = downloader.download()
# Returns: List[str] - List of downloaded file paths
```

#### get_download_manifest()

Get manifest of files to be downloaded without actually downloading.

```python
manifest = downloader.get_download_manifest()
# Returns: List[dict] - List of file specifications
# Each dict contains: source_path, destination_path, lead_time, forecast_time
```

#### verify_downloads()

Verify that downloaded files exist and are accessible.

```python
results = downloader.verify_downloads(downloaded_files)
# Returns: dict with keys:
#   - total: int - Total number of files
#   - exists: int - Number of existing files
#   - missing: List[str] - List of missing file paths
```

### GribProcessor

Process GRIB files and convert to Zarr format.

```python
from nwp_download import GribProcessor, ProcessConfig

processor = GribProcessor(config=ProcessConfig(...))
```

**Methods:**

#### process()

Process GRIB files and write to Zarr.

```python
output_path = processor.process()
# Returns: str - Path to output Zarr archive
```

#### inspect_grib_files()

Inspect GRIB files and return metadata.

```python
metadata = processor.inspect_grib_files()
# Returns: dict with keys:
#   - num_files: int - Number of GRIB files found
#   - variables: List[str] - Available variables
#   - dimensions: dict - Dimension sizes
#   - coordinates: List[str] - Coordinate names
#   - sample_file: str - Path to first file
```

## Data Source Classes

### GFSSource

GFS data source configuration.

```python
from nwp_download.sources import GFSSource
from datetime import datetime

source = GFSSource(
    product="gfs",
    resolution="0p25",
    forecast_time=datetime(2024, 1, 1, 0),
    cycle="00z",
    max_lead_time=120,
    source_bucket="gcp-public-data-arco-era5",
    destination_bucket="your-bucket-name",
    destination_prefix="gfs/",
)

file_list = source.get_file_list()
# Returns: List[GribFileSpec]
```

**Lead Time Intervals:**

- 0-120h: hourly
- 120-240h: 3-hourly
- 240-384h: 12-hourly

### ECMWFSource

ECMWF data source configuration.

```python
from nwp_download.sources import ECMWFSource
from datetime import datetime

source = ECMWFSource(
    product="ecmwf-hres",
    resolution="0p1",
    forecast_time=datetime(2024, 1, 1, 0),
    cycle="00z",
    max_lead_time=240,
    source_bucket="ecmwf-public-data",
    destination_bucket="your-bucket-name",
    destination_prefix="ecmwf/",
)

file_list = source.get_file_list()
```

**Lead Time Intervals:**

HRES:
- 0-90h: hourly
- 90-240h: 3-hourly

ENS:
- 0-144h: 3-hourly
- 144-360h: 6-hourly

### create_data_source()

Factory function to create appropriate data source.

```python
from nwp_download.sources import create_data_source
from datetime import datetime

source = create_data_source(
    product="gfs",
    resolution="0p25",
    forecast_time=datetime(2024, 1, 1, 0),
    cycle="00z",
    max_lead_time=120,
    source_bucket="gcp-public-data-arco-era5",
    destination_bucket="your-bucket-name",
    destination_prefix="gfs/",
)
```

## Utility Functions

### GCS Utilities

```python
from nwp_download.utils import (
    parse_gcs_path,
    is_gcs_path,
    gcs_blob_exists,
    copy_gcs_blob,
    download_gcs_file,
    upload_gcs_file,
)

# Parse GCS path
bucket, blob = parse_gcs_path("gs://bucket/path/to/file")

# Check if path is GCS
if is_gcs_path(path):
    # Handle GCS path
    pass

# Check if blob exists
exists = gcs_blob_exists("bucket-name", "path/to/blob")

# Copy blob
success = copy_gcs_blob(
    source_bucket="source-bucket",
    source_blob="source/path",
    dest_bucket="dest-bucket",
    dest_blob="dest/path",
)

# Download file
from pathlib import Path
success = download_gcs_file(
    bucket_name="bucket-name",
    blob_name="path/to/blob",
    local_path=Path("/local/path"),
)

# Upload file
success = upload_gcs_file(
    local_path=Path("/local/path"),
    bucket_name="bucket-name",
    blob_name="path/to/blob",
)
```

## CLI Commands

### nwp-download download

Download GRIB files from cloud archives.

```bash
nwp-download download \
    --product gfs \
    --resolution 0p25 \
    --time 2024-01-01T00:00:00 \
    --cycle 00z \
    --max-lead-time 120 \
    --source-bucket gcp-public-data-arco-era5 \
    --dest-bucket your-bucket-name \
    --dest-prefix nwp-data/ \
    --overwrite \
    --max-workers 10 \
    --dry-run
```

**Options:**

- `--product`: NWP product (gfs, ecmwf-hres, ecmwf-ens) [required]
- `--resolution`: Model resolution [required]
- `--time`: Forecast initialization time (ISO format) [required]
- `--cycle`: Forecast cycle (00z, 06z, 12z, 18z) [required]
- `--max-lead-time`: Maximum lead time in hours [required]
- `--source-bucket`: Source GCS bucket [required]
- `--dest-bucket`: Destination GCS bucket [required]
- `--dest-prefix`: Optional prefix for destination paths
- `--overwrite`: Overwrite existing files
- `--max-workers`: Number of parallel workers (default: 10)
- `--dry-run`: Show what would be downloaded

### nwp-download process

Process GRIB files and convert to Zarr.

```bash
nwp-download process \
    --grib-path gs://bucket/grib/ \
    --variables t2m,u10,v10,tp \
    --output gs://bucket/output.zarr \
    --filter-keys '{"typeOfLevel": "surface"}' \
    --chunks '{"time": 1, "latitude": 100}' \
    --compression default \
    --overwrite \
    --inspect
```

**Options:**

- `--grib-path`: Path to GRIB files [required]
- `--variables`: Comma-separated list of variables [required]
- `--output`: Output path for Zarr archive [required]
- `--filter-keys`: GRIB filter keys as JSON string
- `--chunks`: Chunking specification as JSON string
- `--compression`: Compression algorithm (default, zstd, lz4, none)
- `--overwrite`: Overwrite existing Zarr archive
- `--inspect`: Inspect GRIB files without processing

### nwp-download run

Run complete workflow from configuration file.

```bash
nwp-download run \
    --config config.yaml \
    --skip-download \
    --skip-process \
    --max-workers 10
```

**Options:**

- `--config`: Path to YAML configuration file [required]
- `--skip-download`: Skip download step
- `--skip-process`: Skip process step
- `--max-workers`: Number of parallel workers (default: 10)

### nwp-download init-config

Generate a sample configuration file.

```bash
nwp-download init-config \
    --product gfs \
    --resolution 0p25 \
    --output config.yaml
```

**Options:**

- `--product`: NWP product (default: gfs)
- `--resolution`: Model resolution (default: 0p25)
- `--output`: Output configuration file path (default: config.yaml)

## Common Variables

### GFS Variables

Surface variables:
- `t2m`: 2-meter temperature (K)
- `d2m`: 2-meter dewpoint temperature (K)
- `u10`: 10-meter U wind component (m/s)
- `v10`: 10-meter V wind component (m/s)
- `tp`: Total precipitation (m)
- `msl`: Mean sea level pressure (Pa)
- `sp`: Surface pressure (Pa)
- `tcc`: Total cloud cover (0-1)

Pressure level variables:
- `t`: Temperature (K)
- `u`: U wind component (m/s)
- `v`: V wind component (m/s)
- `z`: Geopotential (m²/s²)
- `r`: Relative humidity (%)

### ECMWF Variables

Similar to GFS, with additional variables:
- `sst`: Sea surface temperature (K)
- `cape`: Convective available potential energy (J/kg)
- `cin`: Convective inhibition (J/kg)

## Error Handling

All methods may raise exceptions:

- `ValueError`: Invalid configuration or parameters
- `FileNotFoundError`: GRIB files not found
- `google.cloud.exceptions.GoogleCloudError`: GCS operation failures
- `xarray.backends.BackendEntryNotFound`: cfgrib not available

Example error handling:

```python
from nwp_download import GribDownloader, DownloadConfig

try:
    config = DownloadConfig(...)
    downloader = GribDownloader(config)
    files = downloader.download()
except ValueError as e:
    print(f"Configuration error: {e}")
except Exception as e:
    print(f"Download failed: {e}")
```
