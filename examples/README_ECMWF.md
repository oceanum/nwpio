# ECMWF Open Data Configuration

This configuration downloads ECMWF IFS operational forecast data directly from AWS S3 to your local VM.

## Data Source

- **Provider**: ECMWF Open Data
- **Location**: AWS S3 bucket `s3://ecmwf-forecasts` (public, no authentication required)
- **Region**: eu-central-1
- **Format**: GRIB2
- **Resolution**: 0.25° (since Feb 2024)
- **Cycles**: 00z and 12z only (twice daily)
- **Latency**: ~6-8 hours after cycle time

## Cost Analysis

**Direct AWS S3 → VM download (this implementation):**
- ✅ AWS S3 egress: **FREE** (public dataset)
- ✅ No storage costs
- ✅ No GCS egress costs
- **Total cost: $0**

**Alternative (via GCS mirror):**
- ❌ GCS storage: ~$4-6/month
- ❌ GCS egress: additional costs
- **Total cost: $4-6+/month**

## Lead Time Structure

**Important**: The code automatically discovers available timesteps from AWS S3. You only need to specify `max_lead_time` - the maximum forecast horizon you want to download.

### ECMWF Open Data (AWS S3)
The actual timestep intervals are determined by ECMWF and may vary:
- **Typical pattern**: 3-hourly for short range, 6-hourly for longer range
- **Example**: 0, 3, 6, 9, 12... (3-hourly)
- The code will download **all available files up to your `max_lead_time`**

### Configuration
```yaml
download:
  max_lead_time: 72  # Downloads all files from 0h to 72h, whatever timesteps exist
```

## Usage

### Basic Usage

```bash
# Download and process ECMWF 10m winds
CYCLE="2025-10-17T00:00:00" nwpio run \
    --config examples/config-ecmwf-wind10m.yaml \
    --max-workers 8

# Or use environment variables for both config and cycle
export CONFIG="examples/config-ecmwf-wind10m.yaml"
export CYCLE="2025-10-17T00:00:00"
nwpio run --max-workers 8
```

### With Custom Lead Time

Edit the config to extend forecast range:

```yaml
download:
  max_lead_time: 240  # Full 10-day forecast
```

### For Ensemble Data

Change product to ensemble:

```yaml
download:
  product: ecmwf-ens
  max_lead_time: 144
```

## Data Flow

```
AWS S3 (ecmwf-forecasts)
    ↓ (direct download, no cost)
Local VM (/tmp/nwp-data)
    ↓ (process with cfgrib/xarray)
GCS Zarr output (oceanum-data-dev)
```

## File Structure

### Source (AWS S3)
```
s3://ecmwf-forecasts/
└── 20251017/
    └── 00z/
        └── ifs/
            └── 0p25/
                └── oper/
                    ├── 20251017000000-0h-oper-fc.grib2
                    ├── 20251017000000-1h-oper-fc.grib2
                    └── ...
```

### Local Download
```
/tmp/nwp-data/
└── ecmwf/
    └── hres/
        └── 0p25/
            └── 20251017/
                └── 00/
                    ├── ecmwf.hres.00z.0p25.f000.grib
                    ├── ecmwf.hres.00z.0p25.f001.grib
                    └── ...
```

## Dependencies

The following packages are required (already in pyproject.toml):
- `s3fs` - AWS S3 filesystem interface
- `fsspec` - Unified filesystem interface
- `cfgrib` - GRIB file reading
- `xarray` - Data processing
- `zarr` - Output format

Install with:
```bash
pip install -e .
```

## Validation

The config includes `validate_before_download: true` which checks that all files are available before starting the download. This is important because:

1. ECMWF data has 6-8 hour latency
2. Files are uploaded incrementally
3. Prevents partial downloads

## Troubleshooting

### Files not available
```
ERROR: Missing GRIB files for cycle
```
**Solution**: ECMWF data takes 6-8 hours to become available. Wait and retry.

### S3 connection timeout
```
ERROR: Failed to download from S3
```
**Solution**: 
- Check internet connection
- Reduce `--max-workers` to 4 or less
- AWS S3 is in eu-central-1 (may be slower from some regions)

### Invalid cycle time
```
ERROR: ECMWF cycles are only available at 00z and 12z
```
**Solution**: Use cycle times ending in 00:00:00 or 12:00:00 only.

## Performance Tips

1. **Parallel downloads**: Use `--max-workers 8` for faster downloads
2. **Local processing**: Set `destination_bucket: null` to download directly to VM
3. **Cleanup**: Set `cleanup_grib: true` to delete GRIB files after processing
4. **Chunking**: Adjust `chunks` in config for your access pattern

## Resources

- [ECMWF Open Data Documentation](https://confluence.ecmwf.int/display/DAC/ECMWF+open+data)
- [AWS Registry](https://registry.opendata.aws/ecmwf-forecasts/)
- [Dissemination Schedule](https://confluence.ecmwf.int/display/DAC/Dissemination+schedule)
