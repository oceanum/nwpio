# Timestamp Feature for Zarr Output Paths

## Overview

The Zarr output path supports dynamic timestamp placeholders that are automatically replaced based on the forecast data being processed. This allows you to organize multiple forecast cycles in a common directory with unique filenames.

## Available Placeholders

| Placeholder | Description | Example Output |
|-------------|-------------|----------------|
| `{timestamp}` | Custom formatted timestamp | `20240101_000000` |
| `{date}` | Date in YYYYMMDD format | `20240101` |
| `{time}` | Time in HHMMSS format | `000000` |
| `{cycle}` | Forecast cycle | `00z`, `06z`, `12z`, `18z` |

## Configuration

### Basic Usage

```yaml
process:
  output_path: gs://bucket/forecasts/gfs_{date}_{cycle}.zarr
```

This will create files like:
- `gs://bucket/forecasts/gfs_20240101_00z.zarr`
- `gs://bucket/forecasts/gfs_20240101_06z.zarr`
- `gs://bucket/forecasts/gfs_20240101_12z.zarr`

### Custom Timestamp Format

```yaml
process:
  output_path: gs://bucket/forecasts/forecast_{timestamp}.zarr
  timestamp_format: "%Y-%m-%d_%H%M"
```

This will create files like:
- `gs://bucket/forecasts/forecast_2024-01-01_0000.zarr`
- `gs://bucket/forecasts/forecast_2024-01-01_0600.zarr`

### Multiple Placeholders

```yaml
process:
  output_path: gs://bucket/{date}/gfs_{cycle}_leadtime{time}.zarr
```

This will create files like:
- `gs://bucket/20240101/gfs_00z_leadtime000000.zarr`

## Python API

```python
from nwpio import ProcessConfig, GribProcessor

# Using date and cycle placeholders
config = ProcessConfig(
    grib_path="gs://bucket/grib/",
    variables=["u10", "v10"],
    output_path="gs://bucket/forecasts/gfs_{date}_{cycle}.zarr",
)

processor = GribProcessor(config)
output = processor.process()
print(f"Created: {output}")  # Created: gs://bucket/forecasts/gfs_20240101_00z.zarr
```

## How It Works

1. The processor loads GRIB files and extracts the time coordinate
2. The first timestamp from the dataset is used to populate placeholders
3. Placeholders are replaced before writing the Zarr archive
4. The actual output path is returned by the `process()` method

## Use Cases

### 1. Multiple Cycles in Same Directory

Store all forecast cycles for different times in one directory:

```yaml
output_path: gs://bucket/forecasts/gfs_{date}_{cycle}.zarr
```

Result:
```
gs://bucket/forecasts/
├── gfs_20240101_00z.zarr
├── gfs_20240101_06z.zarr
├── gfs_20240101_12z.zarr
└── gfs_20240101_18z.zarr
```

### 2. Date-Based Organization

Organize by date with subdirectories:

```yaml
output_path: gs://bucket/{date}/forecast_{cycle}.zarr
```

Result:
```
gs://bucket/
├── 20240101/
│   ├── forecast_00z.zarr
│   ├── forecast_06z.zarr
│   └── forecast_12z.zarr
└── 20240102/
    ├── forecast_00z.zarr
    └── forecast_06z.zarr
```

### 3. Product and Cycle Naming

Include product information in the filename:

```yaml
output_path: gs://bucket/forecasts/{product}_{resolution}_{date}_{cycle}.zarr
```

Note: `{product}` and `{resolution}` are not automatic placeholders, but you can construct the path in your workflow.

## Important Notes

1. **Timestamp Source**: The timestamp is extracted from the GRIB data itself (first time coordinate)
2. **No Placeholders**: If no placeholders are used, the path is used as-is
3. **GCS and Local**: Works with both GCS paths (`gs://...`) and local paths
4. **Overwrite Protection**: The `overwrite` setting still applies to the final path

## Timestamp Format Strings

The `timestamp_format` field uses Python's `strftime` format codes:

| Code | Meaning | Example |
|------|---------|---------|
| `%Y` | Year (4 digits) | `2024` |
| `%m` | Month (2 digits) | `01` |
| `%d` | Day (2 digits) | `15` |
| `%H` | Hour (24-hour, 2 digits) | `00` |
| `%M` | Minute (2 digits) | `30` |
| `%S` | Second (2 digits) | `00` |
| `%Y%m%d` | Date compact | `20240115` |
| `%Y-%m-%d` | Date with dashes | `2024-01-15` |

Default format: `%Y%m%d_%H%M%S` → `20240115_003000`

## Examples

### Example 1: Simple Date and Cycle

```yaml
process:
  grib_path: gs://bucket/grib/20240101/00/
  variables: [u10, v10]
  output_path: gs://bucket/output/gfs_{date}_{cycle}.zarr
```

Output: `gs://bucket/output/gfs_20240101_00z.zarr`

### Example 2: ISO Format Timestamp

```yaml
process:
  grib_path: gs://bucket/grib/
  variables: [t2m, tp]
  output_path: gs://bucket/output/forecast_{timestamp}.zarr
  timestamp_format: "%Y-%m-%dT%H%M%S"
```

Output: `gs://bucket/output/forecast_2024-01-01T000000.zarr`

### Example 3: Hierarchical Organization

```yaml
process:
  grib_path: gs://bucket/grib/
  variables: [u10, v10, t2m]
  output_path: gs://bucket/forecasts/{date}/{cycle}/data.zarr
```

Output: `gs://bucket/forecasts/20240101/00z/data.zarr`

## CLI Usage

The timestamp feature works automatically with the CLI:

```bash
nwpio process \
    --grib-path gs://bucket/grib/ \
    --variables u10,v10 \
    --output "gs://bucket/forecasts/gfs_{date}_{cycle}.zarr"
```

The actual output path will be printed:
```
Created Zarr archive: gs://bucket/forecasts/gfs_20240101_00z.zarr
```

## Troubleshooting

### No Time Coordinate

If the GRIB files don't have a time coordinate, placeholders won't be replaced. Ensure your GRIB files have valid time information.

### Wrong Timestamp

The timestamp is taken from the **first** time value in the dataset. If you're combining multiple files, ensure they're sorted correctly.

### Path Already Exists

If a file already exists at the generated path and `overwrite: false`, the operation will fail. Either:
- Set `overwrite: true`
- Use more specific placeholders to avoid conflicts
- Clean up old files before processing
