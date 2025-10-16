# Configuration

NWPIO can be configured using YAML files, command-line arguments, or Python code.

## Configuration File

The recommended way to configure NWPIO is using a YAML file.

### Generate Sample Config

```bash
nwpio init-config --output config.yaml
```

### Full Configuration Example

```yaml
download:
  # Product: gfs, ecmwf-hres, or ecmwf-ens
  product: gfs
  
  # Resolution: 0p25 (0.25°), 0p50 (0.5°), 1p00 (1.0°)
  resolution: 0p25
  
  # Forecast initialization time (cycle)
  # Hour must be 0, 6, 12, or 18 (ECMWF: 0 or 12 only)
  cycle: '2024-01-01T00:00:00'
  
  # Maximum lead time in hours
  max_lead_time: 120
  
  # Source GCS bucket (public archive)
  source_bucket: global-forecast-system
  
  # Destination GCS bucket (your bucket)
  destination_bucket: your-bucket-name
  
  # Optional prefix for destination paths
  destination_prefix: nwp-data/
  
  # Overwrite existing files
  overwrite: false

process:
  # Path to GRIB files
  grib_path: gs://your-bucket-name/nwp-data/
  
  # Variables to extract
  variables:
    - u10
    - v10
    - t2m
    - tp
  
  # Output Zarr path with formatting
  output_path: gs://your-bucket-name/forecast_{cycle:%Y%m%d}_{cycle:%Hz}.zarr
  
  # Write locally first, then upload (helps with network issues)
  write_local_first: true
  
  # Optional: custom temp directory
  local_temp_dir: null
  
  # Optional: GRIB key filters
  filter_by_keys: null
  
  # Optional: Zarr chunking
  chunks: null
  
  # Overwrite existing Zarr archive
  overwrite: false

# Delete GRIB files after processing
cleanup_grib: false
```

## Download Configuration

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `product` | string | NWP product: `gfs`, `ecmwf-hres`, `ecmwf-ens` |
| `resolution` | string | Model resolution: `0p25`, `0p50`, `1p00` |
| `cycle` | datetime | Forecast initialization time (ISO format) |
| `max_lead_time` | integer | Maximum lead time in hours |
| `source_bucket` | string | Source GCS bucket name |
| `destination_bucket` | string | Destination GCS bucket name |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `destination_prefix` | string | `""` | Prefix for destination paths |
| `overwrite` | boolean | `false` | Overwrite existing files |

### Cycle Constraints

- **GFS**: 00z, 06z, 12z, 18z (max 384 hours)
- **ECMWF HRES**: 00z, 12z (max 240 hours)
- **ECMWF ENS**: 00z, 12z (max 360 hours)

## Process Configuration

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `grib_path` | string | Path to GRIB files (local or GCS) |
| `variables` | list | Variables to extract |
| `output_path` | string | Output Zarr path (supports formatting) |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `write_local_first` | boolean | `false` | Write locally then upload |
| `local_temp_dir` | string | system temp | Custom temp directory |
| `filter_by_keys` | dict | `null` | GRIB key filters |
| `chunks` | dict | `null` | Zarr chunking specification |
| `overwrite` | boolean | `false` | Overwrite existing Zarr |

### Output Path Formatting

Use Python datetime formatting in the output path:

```yaml
# Date and cycle hour
output_path: gs://bucket/gfs_{cycle:%Y%m%d}_{cycle:%Hz}.zarr
# Result: gfs_20240101_00z.zarr

# ISO format
output_path: gs://bucket/gfs_{cycle:%Y-%m-%d_%H%M}.zarr
# Result: gfs_2024-01-01_0000.zarr

# Compact
output_path: gs://bucket/gfs_{cycle:%Y%m%d%H}.zarr
# Result: gfs_2024010100.zarr
```

See [Output Path Formatting](../advanced/formatting.md) for more details.

## CLI Configuration

Override config file settings with CLI arguments:

```bash
nwpio run --config config.yaml --skip-download
nwpio run --config config.yaml --skip-process
```

## Python Configuration

```python
from datetime import datetime
from nwpio.config import DownloadConfig, ProcessConfig, WorkflowConfig

# Download config
download = DownloadConfig(
    product="gfs",
    resolution="0p25",
    cycle=datetime(2024, 1, 1, 0),
    max_lead_time=120,
    source_bucket="global-forecast-system",
    destination_bucket="your-bucket",
)

# Process config
process = ProcessConfig(
    grib_path="gs://your-bucket/nwp-data/",
    variables=["u10", "v10", "t2m"],
    output_path="gs://your-bucket/forecast_{cycle:%Y%m%d}_{cycle:%Hz}.zarr",
    write_local_first=True,
)

# Combined workflow config
workflow = WorkflowConfig(
    download=download,
    process=process,
    cleanup_grib=False,
)

# Load from YAML
from pathlib import Path
workflow = WorkflowConfig.from_yaml(Path("config.yaml"))

# Save to YAML
workflow.to_yaml(Path("config.yaml"))
```

## Environment Variables

Set Google Cloud credentials:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

## Validation

NWPIO validates all configuration at runtime using Pydantic:

```python
from nwpio.config import DownloadConfig

# This will raise a validation error
config = DownloadConfig(
    product="gfs",
    cycle=datetime(2024, 1, 1, 3),  # Invalid hour (must be 0, 6, 12, 18)
    # ... other fields
)
```

## Next Steps

- [Downloading Data](../guide/downloading.md) - Learn about downloading
- [Processing to Zarr](../guide/processing.md) - Learn about processing
- [API Reference](../api/config.md) - Complete configuration API
