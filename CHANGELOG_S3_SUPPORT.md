# AWS S3 Support Implementation

## Summary

Added native AWS S3 support to nwpio for downloading ECMWF open data directly from AWS, eliminating the need for an intermediate GCS mirror.

## Motivation

ECMWF open data is hosted on AWS S3 (`s3://ecmwf-forecasts`), not GCS. Previously, users would need to:
1. Sync data from AWS S3 to their own GCS bucket (incurring storage costs)
2. Download from GCS to their VM (incurring egress costs)
3. Process the data

This was wasteful and expensive (~$4-6/month in unnecessary costs).

## Changes

### 1. Dependencies (`pyproject.toml`, `requirements.txt`)
- Added `s3fs>=2023.1.0` for AWS S3 filesystem support

### 2. Downloader (`nwpio/downloader.py`)
- Added `parse_cloud_path()` helper to handle both `gs://` and `s3://` paths
- Updated `validate_availability()` to detect and use appropriate filesystem (GCS or S3)
- Updated `_download_file()` to support:
  - S3 → Local downloads (anonymous access)
  - S3 → GCS copies (for archival)
  - Existing GCS → Local and GCS → GCS flows

### 3. ECMWF Source (`nwpio/sources.py`) - **Dynamic File Discovery**
- **NEW**: `_discover_s3_files()` - Lists actual files from S3 and discovers timesteps automatically
- **Timestep agnostic**: No longer assumes fixed intervals (hourly/3-hourly/6-hourly)
- Downloads all available files up to `max_lead_time`, regardless of timestep
- Path format: `s3://ecmwf-forecasts/YYYYMMDD/HHz/ifs/0p25/oper/YYYYMMDDHHmmss-Lh-oper-fc.grib2`
- Falls back to GCS paths for mirrored data
- Skips validation file check for S3 sources (returns `None` from `get_next_lead_time()`)

### 4. Configuration (`examples/config-ecmwf-wind10m.yaml`)
- Updated to use `source_bucket: ecmwf-forecasts` (AWS S3)
- Downloads directly to local VM (`destination_bucket: null`)
- No intermediate GCS storage required

### 5. Documentation (`examples/README_ECMWF.md`)
- Complete guide for ECMWF data access
- Cost comparison (AWS direct: $0 vs GCS mirror: $4-6/month)
- Usage examples and troubleshooting

## Benefits

1. **Zero cost**: AWS S3 public data egress is free
2. **Simpler workflow**: Direct download, no sync step
3. **Faster**: One network hop instead of two
4. **Flexible**: Still supports GCS mirrors if needed

## Usage

```bash
# Install dependencies
pip install -e .

# Download and process ECMWF 10m winds
CYCLE="2025-10-17T00:00:00" nwpio run \
    --config examples/config-ecmwf-wind10m.yaml \
    --max-workers 8
```

## Data Flow

**Before (with GCS mirror):**
```
AWS S3 → GCS mirror → VM → Process → GCS output
         (storage $)  (egress $)
```

**After (direct S3):**
```
AWS S3 → VM → Process → GCS output
  (free)
```

## Backward Compatibility

- Existing GFS configs unchanged (still use GCS)
- Existing ECMWF configs with GCS mirrors still work
- S3 support is opt-in via `source_bucket` setting

## Testing

To test the implementation:

```bash
# Validate files are available (doesn't download)
CYCLE="2025-10-17T00:00:00" nwpio run \
    --config examples/config-ecmwf-wind10m.yaml \
    --validate-only

# Download a small subset
# Edit config: max_lead_time: 3
CYCLE="2025-10-17T00:00:00" nwpio run \
    --config examples/config-ecmwf-wind10m.yaml \
    --max-workers 4
```

## Future Enhancements

1. Support for other S3-hosted datasets (NOAA on AWS)
2. Configurable S3 credentials for private buckets
3. Direct HTTP/HTTPS download support
4. Azure Blob Storage support

## Notes

- S3 access is anonymous (no credentials required)
- ECMWF data has 6-8 hour latency after cycle time
- Only 00z and 12z cycles available
- Files are in GRIB2 format
