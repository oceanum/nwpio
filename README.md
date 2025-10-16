# NWPIO

A Python library for downloading and processing Numerical Weather Prediction (NWP) forecast data from cloud archives.

## Features

- **Download GRIB files** from cloud archives (GCS) for NWP models such as GFS and ECMWF
- **File availability validation** - Ensures all files are complete before downloading (see [FILE_VALIDATION.md](FILE_VALIDATION.md))
- **Multi-process workflow** - Download once, process multiple variable sets efficiently
- **Parallel operations** - Fast downloads (8 workers) and uploads (16 workers)
- **Flexible configuration** for product type, resolution, forecast cycles, and lead times
- **Extract variables** from GRIB files using xarray and cfgrib with smart filtering
- **Convert to Zarr** format for efficient storage and access
- **Cycle-based formatting** - Dynamic paths with `{cycle:%Y%m%d}` placeholders
- **CLI interface** for easy integration with deployment workflows
- **Automatic cleanup** - Optional GRIB file deletion after processing

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
    output_path: gs://your-bucket/wind_{cycle:%Y%m%d}_{cycle:%Hz}.zarr
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
    output_path: gs://your-bucket/wind10m_{cycle:%Y%m%d}_{cycle:%Hz}.zarr
    variables: [u10, v10]
    max_upload_workers: 16
    
  # Process 2: 2m temperature and humidity
  - filter_by_keys:
      typeOfLevel: heightAboveGround
      level: 2
    output_path: gs://your-bucket/surface_{cycle:%Y%m%d}_{cycle:%Hz}.zarr
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
