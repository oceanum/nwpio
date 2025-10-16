# Downloading Data

Learn how to download GRIB files from cloud archives.

## Overview

NWPIO downloads GRIB files from public cloud archives (like GCS) to your own bucket using server-side copy operations. No data passes through your local machine during downloads.

## Basic Download

```bash
nwpio download \
    --product gfs \
    --resolution 0p25 \
    --cycle 2024-01-01T00:00:00 \
    --max-lead-time 120 \
    --source-bucket global-forecast-system \
    --dest-bucket your-bucket-name
```

## Products

### GFS (Global Forecast System)

```bash
nwpio download \
    --product gfs \
    --resolution 0p25 \
    --cycle 2024-01-01T00:00:00 \
    --max-lead-time 384 \
    --source-bucket global-forecast-system \
    --dest-bucket your-bucket
```

**Available:**
- Resolutions: 0.25°, 0.5°, 1.0°
- Cycles: 00z, 06z, 12z, 18z
- Max lead time: 384 hours

### ECMWF HRES

```bash
nwpio download \
    --product ecmwf-hres \
    --resolution 0p25 \
    --cycle 2024-01-01T00:00:00 \
    --max-lead-time 240 \
    --source-bucket your-ecmwf-bucket \
    --dest-bucket your-bucket
```

**Available:**
- Resolutions: 0.1°, 0.25°
- Cycles: 00z, 12z
- Max lead time: 240 hours

### ECMWF ENS (Ensemble)

```bash
nwpio download \
    --product ecmwf-ens \
    --resolution 0p25 \
    --cycle 2024-01-01T00:00:00 \
    --max-lead-time 360 \
    --source-bucket your-ecmwf-bucket \
    --dest-bucket your-bucket
```

**Available:**
- Resolutions: 0.25°, 0.5°
- Cycles: 00z, 12z
- Max lead time: 360 hours

## Options

### Destination Prefix

Organize downloaded files with a prefix:

```bash
nwpio download \
    --dest-prefix nwp-data/gfs/ \
    # ... other options
```

### Overwrite Existing Files

```bash
nwpio download \
    --overwrite \
    # ... other options
```

### Parallel Workers

Control download parallelism:

```bash
nwpio download \
    --max-workers 20 \
    # ... other options
```

Default is 10 workers.

### Dry Run

Preview what will be downloaded:

```bash
nwpio download \
    --dry-run \
    # ... other options
```

## Python API

```python
from datetime import datetime
from nwpio import GribDownloader
from nwpio.config import DownloadConfig

# Configure download
config = DownloadConfig(
    product="gfs",
    resolution="0p25",
    cycle=datetime(2024, 1, 1, 0),
    max_lead_time=120,
    source_bucket="global-forecast-system",
    destination_bucket="your-bucket",
    destination_prefix="nwp-data/",
    overwrite=False,
)

# Create downloader
downloader = GribDownloader(config, max_workers=10)

# Download files
files = downloader.download()
print(f"Downloaded {len(files)} files")

# Verify downloads
verification = downloader.verify_downloads(files)
print(f"Verified: {verification['exists']}/{verification['total']}")
```

### Get Download Manifest

Preview files without downloading:

```python
manifest = downloader.get_download_manifest()
for item in manifest:
    print(f"{item['source_path']} -> {item['destination_path']}")
```

## File Organization

Downloaded files are organized by product:

### GFS

```
gs://your-bucket/nwp-data/gfs/0p25/20240101/00/
├── gfs.t00z.pgrb2.0p25.f000
├── gfs.t00z.pgrb2.0p25.f001
├── gfs.t00z.pgrb2.0p25.f002
└── ...
```

### ECMWF

```
gs://your-bucket/nwp-data/ecmwf/hres/0p25/20240101/00/
├── ecmwf.hres.00z.0p25.f000.grib
├── ecmwf.hres.00z.0p25.f003.grib
└── ...
```

## Lead Time Intervals

Different products have different output intervals:

### GFS
- 0-120h: Hourly
- 120-240h: 3-hourly
- 240-384h: 12-hourly

### ECMWF HRES
- 0-90h: Hourly
- 90-240h: 3-hourly

### ECMWF ENS
- 0-144h: 3-hourly
- 144-360h: 6-hourly

## Best Practices

mkdir -p docs/{getting-started,guide,api,advanced,about}! tip "Start Small"
    Test with a short lead time (6-24 hours) before downloading full datasets.

mkdir -p docs/{getting-started,guide,api,advanced,about}! tip "Use Dry Run"
    Always preview with `--dry-run` first to verify paths and file counts.

mkdir -p docs/{getting-started,guide,api,advanced,about}! tip "Monitor Costs"
    GCS-to-GCS copies incur egress charges. Monitor your GCP billing.

mkdir -p docs/{getting-started,guide,api,advanced,about}! warning "Source Bucket Access"
    Ensure you have read access to the source bucket. Public buckets like `global-forecast-system` are freely accessible.

## Troubleshooting

**Source file not found**

The requested data may not be available yet. Check:
- Forecast cycle time is in the past
- Data exists in the source bucket
- Correct bucket name and path

**Permission denied**

Verify your GCS permissions:
```bash
gsutil ls gs://source-bucket/
gsutil ls gs://destination-bucket/
```

**Slow downloads**

Increase parallel workers:
```bash
nwpio download --max-workers 20 ...
```

## Next Steps

- [Processing to Zarr](processing.md) - Convert GRIB to Zarr
- [Data Sources](data-sources.md) - Learn about data sources
- [API Reference](../api/downloader.md) - Complete API docs
