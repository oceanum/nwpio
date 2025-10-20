# NWPIO

A Python library for downloading and processing Numerical Weather Prediction (NWP) forecast data from cloud archives.

## Features

### Data Download
- **Multiple NWP models** - GFS, ECMWF HRES/ENS support
- **Flexible resolutions** - 0.1°, 0.25°, 0.5°, 1.0° depending on product
- **Configurable cycles** - 00z, 06z, 12z, 18z with variable lead times (up to 384h)
- **Parallel downloads** - Configurable workers for fast transfers
- **GCS-to-GCS copying** - No local storage needed for large files
- **File validation** - Ensures all files are complete before downloading
- **Smart skipping** - Avoid re-downloading existing files

### GRIB Processing
- **Variable extraction** - Select specific variables from GRIB files
- **Time concatenation** - Combine multiple files along time dimension
- **Zarr conversion** - Efficient chunked storage format
- **Configurable chunking** - Optimize for your access patterns
- **Compression support** - Multiple algorithms (zstd, lz4)
- **GRIB key filtering** - Filter by level, type, etc.
- **Parallel GRIB loading** - Fast processing with multiple workers

### Production Ready
- **Type-safe configuration** - Pydantic models with validation
- **Flexible cycle configuration** - CLI (`--cycle`), environment (`$CYCLE`), or config file
- **Multi-process workflow** - Download once, process multiple variable sets
- **Cycle-based formatting** - Dynamic paths with `{cycle:%Y%m%d}` placeholders
- **Comprehensive logging** - Track progress and debug issues
- **Error handling** - Robust recovery and retry logic
- **Automatic cleanup** - Optional GRIB file deletion after processing
- **Docker support** - Container-ready for cloud deployment

## Installation

```bash
pip install -e .
```

For development:
```bash
pip install -e ".[dev]"
```

## Quick Start

### Download GRIB files

```python
from nwpio import GribDownloader, DownloadConfig
from datetime import datetime

config = DownloadConfig(
    product="gfs",
    resolution="0p25",
    forecast_time=datetime(2024, 1, 1, 0),
    cycle="00z",
    max_lead_time=120,  # hours
    source_bucket="gcp-public-data-arco-era5",
    destination_bucket="your-bucket-name",
)

downloader = GribDownloader(config)
downloaded_files = downloader.download()
```

### Process GRIB to Zarr

```python
from nwpio import GribProcessor, ProcessConfig

config = ProcessConfig(
    grib_files=downloaded_files,
    variables=["t2m", "u10", "v10", "tp"],
    output_path="gs://your-bucket/output.zarr",
)

processor = GribProcessor(config)
processor.process()
```

### Using the CLI

```bash
# Download GRIB files
nwpio download \
    --product gfs \
    --resolution 0p25 \
    --time 2024-01-01T00:00:00 \
    --cycle 00z \
    --max-lead-time 120 \
    --source-bucket gcp-public-data-arco-era5 \
    --dest-bucket your-bucket-name

# Process GRIB to Zarr
nwpio process \
    --grib-path gs://your-bucket/grib/ \
    --variables t2m,u10,v10,tp \
    --output gs://your-bucket/output.zarr

# Combined workflow
nwpio run \
    --config config.yaml
```

### Configuration File Example

#### Single Process Configuration
```yaml
# config.yaml
download:
  product: gfs
  resolution: 0p25
  cycle: "2024-01-01T00:00:00"
  max_lead_time: 6
  source_bucket: global-forecast-system
  destination_bucket: your-bucket-name
  destination_prefix: nwp-data/

process:
  - filter_by_keys:
      typeOfLevel: heightAboveGround
      level: 10
    zarr_path: gs://your-bucket/wind_{cycle:%Y%m%d}_{cycle:%Hz}.zarr
    variables: [u10, v10]
    write_local_first: true
    max_upload_workers: 16
```

#### Multi-Process Configuration (Recommended)
Download once, create multiple Zarr archives with different variable sets:

```yaml
# config-multi.yaml
cleanup_grib: true  # Delete GRIB files after all processing

download:
  product: gfs
  resolution: 0p25
  cycle: "2024-01-01T00:00:00"
  max_lead_time: 6
  source_bucket: global-forecast-system
  destination_bucket: your-bucket-name

process:
  # Process 1: 10m winds
  - filter_by_keys:
      typeOfLevel: heightAboveGround
      level: 10
    zarr_path: gs://your-bucket/wind10m_{cycle:%Y%m%d}_{cycle:%Hz}.zarr
    variables: [u10, v10]
    max_upload_workers: 16
    
  # Process 2: 2m temperature and humidity
  - filter_by_keys:
      typeOfLevel: heightAboveGround
      level: 2
    zarr_path: gs://your-bucket/surface_{cycle:%Y%m%d}_{cycle:%Hz}.zarr
    variables: [t2m, d2m]
    max_upload_workers: 16
```

Run with:
```bash
nwpio run --config config-multi.yaml --max-workers 8
```

## Supported Products

### GFS (Global Forecast System)
- Resolutions: 0p25 (0.25°), 0p50 (0.5°), 1p00 (1.0°)
- Cycles: 00z, 06z, 12z, 18z
- Lead times: Up to 384 hours

### ECMWF
- Products: HRES (High Resolution), ENS (Ensemble)
- Resolutions: 0p1 (0.1°), 0p25 (0.25°)
- Cycles: 00z, 12z
- Lead times: Up to 240 hours (HRES), 360 hours (ENS)

## Architecture

```
nwpio/
├── __init__.py
├── config.py          # Configuration models using Pydantic
├── sources.py         # Data source definitions for GFS/ECMWF
├── downloader.py      # GRIB file download logic
├── processor.py       # GRIB to Zarr conversion
├── utils.py           # Utility functions
└── cli.py             # Command-line interface
```

## Requirements

- Python 3.9+
- Google Cloud Storage access (with appropriate credentials)
- GRIB file support (eccodes library)

## License

MIT
