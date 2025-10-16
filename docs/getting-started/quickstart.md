# Quick Start

Get started with NWPIO in 5 minutes!

## Prerequisites

- Python 3.9+
- Google Cloud authentication configured
- Access to GCS buckets

See [Installation](installation.md) for setup instructions.

## CLI Quick Start

### 1. Download GRIB Files

Download 24 hours of GFS forecast data:

```bash
nwpio download \
    --product gfs \
    --resolution 0p25 \
    --cycle 2024-01-01T00:00:00 \
    --max-lead-time 24 \
    --source-bucket global-forecast-system \
    --dest-bucket your-bucket-name
```

### 2. Process to Zarr

Convert GRIB files to Zarr format:

```bash
nwpio process \
    --grib-path gs://your-bucket-name/nwp-data/ \
    --variables u10,v10,t2m \
    --output gs://your-bucket-name/forecast_{cycle:%Y%m%d}_{cycle:%Hz}.zarr \
    --write-local-first
```

### 3. Complete Workflow

Use a configuration file for the full workflow:

```bash
# Generate sample config
nwpio init-config --output config.yaml

# Edit config.yaml with your settings
# Then run:
nwpio run --config config.yaml
```

## Python API Quick Start

```python
from datetime import datetime
from nwpio import GribDownloader, GribProcessor
from nwpio.config import DownloadConfig, ProcessConfig

# Step 1: Download
download_config = DownloadConfig(
    product="gfs",
    resolution="0p25",
    cycle=datetime(2024, 1, 1, 0),  # 00z cycle
    max_lead_time=24,
    source_bucket="global-forecast-system",
    destination_bucket="your-bucket-name",
)

downloader = GribDownloader(download_config)
files = downloader.download()
print(f"Downloaded {len(files)} files")

# Step 2: Process
process_config = ProcessConfig(
    grib_path="gs://your-bucket-name/nwp-data/",
    variables=["u10", "v10", "t2m"],
    output_path="gs://your-bucket-name/forecast_{cycle:%Y%m%d}_{cycle:%Hz}.zarr",
    write_local_first=True,
)

processor = GribProcessor(process_config)
output_path = processor.process()
print(f"Created Zarr archive: {output_path}")
```

## Configuration File

Create `config.yaml`:

```yaml
download:
  product: gfs
  resolution: 0p25
  cycle: '2024-01-01T00:00:00'
  max_lead_time: 24
  source_bucket: global-forecast-system
  destination_bucket: your-bucket-name
  destination_prefix: nwp-data/

process:
  grib_path: gs://your-bucket-name/nwp-data/
  variables:
    - u10
    - v10
    - t2m
  output_path: gs://your-bucket-name/forecast_{cycle:%Y%m%d}_{cycle:%Hz}.zarr
  write_local_first: true

cleanup_grib: false
```

Run with:

```bash
nwpio run --config config.yaml
```

## Common Variables

| Variable | Description |
|----------|-------------|
| `u10` | 10m U wind component |
| `v10` | 10m V wind component |
| `t2m` | 2m temperature |
| `tp` | Total precipitation |
| `msl` | Mean sea level pressure |
| `sp` | Surface pressure |

## Tips

!!! tip "Start Small"
    Begin with a short lead time (6-24 hours) to test your setup before downloading larger datasets.

!!! tip "Use Dry Run"
    Add `--dry-run` to preview what will be downloaded without actually downloading.

!!! tip "Write Local First"
    Use `--write-local-first` when processing to avoid network issues with large Zarr archives.

## Next Steps

- [Configuration Guide](configuration.md) - Learn about all configuration options
- [Downloading Data](../guide/downloading.md) - Detailed download instructions
- [Processing to Zarr](../guide/processing.md) - Advanced processing options
- [Data Sources](../guide/data-sources.md) - Learn about available data sources

## Troubleshooting

**Authentication Error**
```bash
gcloud auth application-default login
```

**Bucket Not Found**

- Verify bucket name is correct
- Check you have read/write permissions

**GRIB Files Not Found**

- Verify the source bucket and date
- Check if data exists for the requested cycle

For more help, see the [User Guide](../guide/downloading.md).
