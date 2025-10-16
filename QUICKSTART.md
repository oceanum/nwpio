# Quick Start Guide

Get started with NWP Download in 5 minutes!

## Installation

```bash
# Install the library
pip install -e .

# Verify installation
nwpio --version
```

## Setup Google Cloud

```bash
# Authenticate with Google Cloud
gcloud auth application-default login

# Or set service account credentials
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

## Basic Usage

### 1. Generate Configuration

```bash
nwpio init-config --output my-config.yaml
```

### 2. Edit Configuration

Edit `my-config.yaml` with your settings:

```yaml
download:
  product: gfs
  resolution: 0p25
  forecast_time: "2024-01-01T00:00:00"
  cycle: 00z
  max_lead_time: 120
  source_bucket: gcp-public-data-arco-era5
  destination_bucket: YOUR-BUCKET-NAME  # Change this!
  destination_prefix: nwp-data/

process:
  grib_path: gs://YOUR-BUCKET-NAME/nwp-data/  # Change this!
  variables:
    - t2m
    - u10
    - v10
    - tp
  output_path: gs://YOUR-BUCKET-NAME/output.zarr  # Change this!
```

### 3. Run Workflow

```bash
# Dry run to preview
nwpio download \
    --product gfs \
    --resolution 0p25 \
    --time 2024-01-01T00:00:00 \
    --cycle 00z \
    --max-lead-time 120 \
    --source-bucket gcp-public-data-arco-era5 \
    --dest-bucket YOUR-BUCKET-NAME \
    --dry-run

# Run complete workflow
nwpio run --config my-config.yaml
```

## Python API

```python
from datetime import datetime
from nwpio import GribDownloader, GribProcessor, DownloadConfig, ProcessConfig

# Download GRIB files
download_config = DownloadConfig(
    product="gfs",
    resolution="0p25",
    forecast_time=datetime(2024, 1, 1, 0),
    cycle="00z",
    max_lead_time=120,
    source_bucket="gcp-public-data-arco-era5",
    destination_bucket="your-bucket-name",
)

downloader = GribDownloader(download_config)
files = downloader.download()

# Process to Zarr
process_config = ProcessConfig(
    grib_path="gs://your-bucket-name/nwp-data/",
    variables=["t2m", "u10", "v10", "tp"],
    output_path="gs://your-bucket-name/output.zarr",
)

processor = GribProcessor(process_config)
processor.process()
```

## Docker Deployment

```bash
# Build image
docker build -t nwpio .

# Run
docker run \
    -v $(pwd)/config.yaml:/config/config.yaml \
    -v ~/.config/gcloud:/root/.config/gcloud \
    nwpio run --config /config/config.yaml
```

## Next Steps

- Read the [full documentation](README.md)
- Check [examples](examples/)
- Review [API reference](docs/API.md)
- See [deployment guide](docs/DEPLOYMENT.md)

## Common Issues

**Authentication Error:**
```bash
gcloud auth application-default login
```

**Bucket Not Found:**
- Verify bucket name is correct
- Check you have permissions to access the bucket

**GRIB Files Not Found:**
- Verify the source bucket path
- Check if data exists for the requested date/time

## Support

For issues and questions:
- Check the documentation in `docs/`
- Review examples in `examples/`
- Open an issue on GitHub
