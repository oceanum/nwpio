# Write Local First Feature

## Overview

The `write_local_first` option allows you to write Zarr archives to a local temporary directory first, then upload them to GCS. This helps avoid network issues that can occur when writing large Zarr archives directly to cloud storage.

## Why Use This Feature?

### Problems with Direct GCS Writes

When writing Zarr archives directly to GCS, you may encounter:

1. **Network Timeouts**: Long-running writes can timeout on unstable connections
2. **Partial Writes**: Network interruptions can leave incomplete archives
3. **Retry Issues**: Failed writes may require re-processing all data
4. **Performance**: Direct cloud writes can be slower than local writes

### Benefits of Write Local First

1. **Reliability**: Local writes are fast and don't depend on network stability
2. **Atomic Uploads**: Upload happens after successful local write
3. **Resume Capability**: Can retry upload without re-processing data
4. **Better Performance**: Local I/O is typically faster than network I/O

## Configuration

### YAML Configuration

```yaml
process:
  grib_path: gs://bucket/grib/
  variables: [u10, v10, t2m]
  output_path: gs://bucket/forecasts/gfs_{date}_{cycle}.zarr
  
  # Enable write local first
  write_local_first: true
  
  # Optional: specify custom temp directory
  local_temp_dir: /tmp/zarr-staging
```

### Python API

```python
from nwpio import ProcessConfig, GribProcessor

config = ProcessConfig(
    grib_path="gs://bucket/grib/",
    variables=["u10", "v10", "t2m"],
    output_path="gs://bucket/forecasts/gfs_{date}_{cycle}.zarr",
    write_local_first=True,
    local_temp_dir="/tmp/zarr-staging",  # Optional
)

processor = GribProcessor(config)
processor.process()
```

### CLI

```bash
nwpio process \
    --grib-path gs://bucket/grib/ \
    --variables u10,v10,t2m \
    --output gs://bucket/forecasts/gfs_20240101_00z.zarr \
    --write-local-first \
    --local-temp-dir /tmp/zarr-staging
```

## How It Works

1. **Create Temp Directory**: Creates a temporary directory (system temp or custom)
2. **Write Locally**: Writes the complete Zarr archive to local disk
3. **Upload to GCS**: Uploads all files in the Zarr archive to GCS
4. **Cleanup**: Removes the temporary directory

### Process Flow

```
GRIB Files (GCS)
    ↓
Load & Process
    ↓
Write to Local Temp
    ↓ (e.g., /tmp/tmpXXXXXX/gfs_20240101_00z.zarr/)
Upload to GCS
    ↓ (gs://bucket/forecasts/gfs_20240101_00z.zarr/)
Cleanup Local Temp
```

## Disk Space Requirements

The temporary directory needs enough space to hold the complete Zarr archive:

- **Small datasets** (few variables, short lead time): ~100 MB - 1 GB
- **Medium datasets** (several variables, 120h lead time): ~1 GB - 5 GB
- **Large datasets** (many variables, 384h lead time): ~5 GB - 20 GB

### Checking Available Space

```bash
# Check available space in /tmp
df -h /tmp

# Check available space in custom directory
df -h /path/to/custom/temp
```

## Configuration Options

### `write_local_first` (bool)

- **Default**: `false`
- **Description**: Enable write-local-first mode
- **When to use**: When experiencing network issues with direct GCS writes

### `local_temp_dir` (str, optional)

- **Default**: System temp directory (e.g., `/tmp` on Linux)
- **Description**: Custom directory for temporary Zarr files
- **When to use**: 
  - When system temp has limited space
  - When you want to control cleanup
  - When you need faster local storage (e.g., SSD)

## Examples

### Example 1: Basic Usage

```yaml
process:
  output_path: gs://bucket/forecast.zarr
  write_local_first: true
```

This will:
- Write to `/tmp/tmpXXXXXX/forecast.zarr/`
- Upload to `gs://bucket/forecast.zarr/`
- Clean up `/tmp/tmpXXXXXX/`

### Example 2: Custom Temp Directory

```yaml
process:
  output_path: gs://bucket/forecast_{date}_{cycle}.zarr
  write_local_first: true
  local_temp_dir: /data/zarr-staging
```

This will:
- Write to `/data/zarr-staging/tmpXXXXXX/forecast_20240101_00z.zarr/`
- Upload to `gs://bucket/forecast_20240101_00z.zarr/`
- Clean up `/data/zarr-staging/tmpXXXXXX/`

### Example 3: Large Dataset

```python
config = ProcessConfig(
    grib_path="gs://bucket/grib/",
    variables=["t", "u", "v", "z", "r"],  # Multiple pressure level variables
    output_path="gs://bucket/large_forecast_{timestamp}.zarr",
    chunks={"time": 1, "latitude": 50, "longitude": 50},
    write_local_first=True,
    local_temp_dir="/mnt/fast-ssd/zarr-temp",  # Use fast SSD
)
```

## Monitoring Progress

The processor logs progress at each stage:

```
INFO - Processing GRIB files from gs://bucket/grib/
INFO - Found 121 GRIB files
INFO - Loading GRIB files: 100%|████████| 121/121
INFO - Combining datasets...
INFO - Writing to Zarr: gs://bucket/forecast_20240101_00z.zarr
INFO - Writing to local temp directory: /tmp/tmpXXXXXX/forecast_20240101_00z.zarr
INFO - Uploading to GCS: gs://bucket/forecast_20240101_00z.zarr
INFO - Uploading 1234 files...
Uploading to GCS: 100%|████████| 1234/1234
INFO - Upload complete
INFO - Cleaning up temp directory: /tmp/tmpXXXXXX
INFO - Processing complete
```

## Error Handling

### Local Write Fails

If the local write fails (e.g., out of disk space):
- Temp directory is cleaned up
- Error is raised
- No upload is attempted

### Upload Fails

If the upload fails (e.g., network error):
- Temp directory is cleaned up
- Error is raised
- You can retry by re-running the process

### Cleanup Fails

If cleanup fails:
- Warning is logged
- Process continues (upload was successful)
- Manual cleanup may be needed

## Performance Comparison

### Direct GCS Write

```
Load GRIB: 2 min
Process: 1 min
Write to GCS: 15 min (network dependent)
Total: ~18 min
```

### Write Local First

```
Load GRIB: 2 min
Process: 1 min
Write Local: 1 min (fast local I/O)
Upload to GCS: 5 min (parallel upload)
Cleanup: 10 sec
Total: ~9 min
```

**Note**: Actual performance depends on:
- Network speed and stability
- Local disk speed
- Dataset size
- GCS region proximity

## Best Practices

1. **Use for Large Datasets**: Most beneficial for datasets > 1 GB
2. **Fast Local Storage**: Use SSD if available for temp directory
3. **Monitor Disk Space**: Ensure adequate space before processing
4. **Network Issues**: Always use when experiencing network problems
5. **Cleanup**: Temp directories are auto-cleaned, but monitor for failures

## Troubleshooting

### Out of Disk Space

**Error**: `No space left on device`

**Solution**:
```yaml
# Use a directory with more space
local_temp_dir: /mnt/large-disk/zarr-temp
```

### Slow Upload

**Issue**: Upload takes very long

**Solutions**:
- Check network bandwidth
- Verify GCS bucket region (use same region as compute)
- Consider using smaller chunks to reduce file count

### Temp Directory Not Cleaned

**Issue**: Temp directories accumulate

**Solution**:
```bash
# Manual cleanup
rm -rf /tmp/tmp*/
rm -rf /path/to/custom/temp/tmp*/
```

## Comparison with Direct Write

| Feature | Direct Write | Write Local First |
|---------|-------------|-------------------|
| Network dependency | High | Low (only upload) |
| Disk space needed | None | Full dataset size |
| Failure recovery | Re-process all | Retry upload only |
| Performance | Slower | Faster (usually) |
| Complexity | Simple | More complex |
| Best for | Small datasets, stable network | Large datasets, unstable network |

## When NOT to Use

- **Small datasets** (< 100 MB): Direct write is fine
- **Limited disk space**: Not enough temp storage
- **Very stable network**: Direct write works well
- **Remote compute**: If compute is far from storage, direct write may be better

## Compression Note

The library now uses xarray's default Zarr compression settings, which provide good compression without requiring manual configuration. This simplifies the configuration and works well for most use cases.
