# NWPIO Features Documentation

## 1. Zarr Overwrite Behavior

### Default Behavior (overwrite: false)
- **Checks if Zarr archive exists** at the output path before processing
- **Raises FileExistsError** if archive already exists
- **Prevents accidental overwrites** of existing data

### Overwrite Mode (overwrite: true)
- **Deletes existing Zarr archive** before uploading new one
- **Ensures clean replacement** of data
- **Useful for reprocessing** the same cycle

### Configuration Example:
```yaml
process:
  - output_path: gs://bucket/wind_{cycle:%Y%m%d}_{cycle:%Hz}.zarr
    overwrite: false  # Raise error if exists (default)
    # overwrite: true  # Delete and replace if exists
```

### Behavior with write_local_first:
When `write_local_first: true`:
1. Checks if GCS destination exists (if `overwrite: false`)
2. Writes Zarr to local temp directory
3. Deletes existing GCS Zarr (if `overwrite: true` and exists)
4. Uploads new Zarr to GCS
5. Cleans up local temp directory

## 2. Variable Lead Time Intervals

The library automatically handles variable time intervals for different forecast models.

### GFS (Global Forecast System)
```
0-120h:   Hourly (1h intervals)
120-240h: 3-hourly intervals
240-384h: 12-hourly intervals
```

**Example:** `max_lead_time: 160` downloads:
- 0, 1, 2, ..., 120 (121 files)
- 123, 126, 129, ..., 159 (13 files)
- **Total: 134 files**

### ECMWF HRES (High Resolution)
```
0-90h:    Hourly (1h intervals)
90-240h:  3-hourly intervals
```

**Example:** `max_lead_time: 160` downloads:
- 0, 1, 2, ..., 90 (91 files)
- 93, 96, 99, ..., 159 (23 files)
- **Total: 114 files**

### ECMWF ENS (Ensemble)
```
0-144h:   3-hourly intervals
144-360h: 6-hourly intervals
```

**Example:** `max_lead_time: 160` downloads:
- 0, 3, 6, ..., 144 (49 files)
- 150, 156 (2 files)
- **Total: 51 files**

### Implementation
The interval logic is handled automatically in the data source classes:
- `GFSSource._generate_lead_times()`
- `ECMWFSource._generate_lead_times()`

You simply specify `max_lead_time` and the library downloads all available timesteps up to that point.

## 3. Cycle-Based Path Formatting

Both `grib_path` and `output_path` support Python datetime formatting using the `{cycle:...}` placeholder.

### Available Formats:
```yaml
{cycle:%Y}       # 2024
{cycle:%m}       # 01
{cycle:%d}       # 15
{cycle:%H}       # 00
{cycle:%Y%m%d}   # 20240115
{cycle:%Hz}      # 00z
{cycle:%Y-%m-%d_%H%M}  # 2024-01-15_0000
```

### Example:
```yaml
download:
  cycle: '2024-01-15T00:00:00'

process:
  - output_path: gs://bucket/gfs_{cycle:%Y%m%d}_{cycle:%Hz}.zarr
    # Resolves to: gs://bucket/gfs_20240115_00z.zarr
```

## 4. Local vs Cloud Downloads

### Local Downloads (Recommended for Processing)
```yaml
download:
  destination_bucket: null  # null = download locally
  local_download_dir: /tmp/nwp-data
```
- Downloads from GCS to local disk
- Fast processing from local files
- Ideal for ephemeral VMs/containers

### Cloud-to-Cloud Copy
```yaml
download:
  destination_bucket: my-bucket  # GCS bucket name
  destination_prefix: nwp-data/
```
- Copies from one GCS bucket to another
- No local storage required
- Useful for data archiving

## 5. Multi-Process Workflow

Download once, create multiple Zarr archives with different variable sets.

### Benefits:
- **Download once** - No redundant downloads
- **Process many times** - Extract different variables
- **Automatic cleanup** - Delete GRIBs after all processing

### Example:
```yaml
cleanup_grib: true  # Delete GRIBs after all processing

download:
  destination_bucket: null
  local_download_dir: /tmp/nwp-data
  max_lead_time: 120

process:
  # Process 1: Surface winds
  - filter_by_keys: {typeOfLevel: heightAboveGround, level: 10}
    output_path: gs://bucket/wind10m_{cycle:%Y%m%d}.zarr
    variables: [u10, v10]
    
  # Process 2: Surface temperature
  - filter_by_keys: {typeOfLevel: heightAboveGround, level: 2}
    output_path: gs://bucket/temp2m_{cycle:%Y%m%d}.zarr
    variables: [t2m, d2m]
    
  # Process 3: Pressure levels
  - filter_by_keys: {typeOfLevel: isobaricInhPa, level: 850}
    output_path: gs://bucket/850mb_{cycle:%Y%m%d}.zarr
    variables: [t, u, v, q]
```

## 6. Parallel Operations

### Parallel Downloads
```yaml
# CLI flag
--max-workers 16  # Number of parallel download workers (default: 4)
```

### Parallel Uploads
```yaml
process:
  - max_upload_workers: 16  # Number of parallel upload workers (default: 16)
```

**Performance:** 8x faster uploads (3m37s → 26s for 51 files)

## 7. GRIB Variable Filtering

Use cfgrib's `filter_by_keys` to extract specific variables efficiently.

### Common Filters:

#### By Level Type and Height:
```yaml
filter_by_keys:
  typeOfLevel: heightAboveGround
  level: 10  # 10m winds
```

#### By Pressure Level:
```yaml
filter_by_keys:
  typeOfLevel: isobaricInhPa
  level: 850  # 850mb level
```

#### Surface Variables:
```yaml
filter_by_keys:
  typeOfLevel: surface
```

### Available Variables by Level:

**heightAboveGround (level: 10):**
- `u10`, `v10` - 10m winds

**heightAboveGround (level: 2):**
- `t2m` - 2m temperature
- `d2m` - 2m dewpoint temperature
- `r2` - 2m relative humidity

**surface:**
- `sp` - Surface pressure
- `msl` - Mean sea level pressure
- `tp` - Total precipitation
- `sst` - Sea surface temperature

**isobaricInhPa (level: 850/700/500/...):**
- `t` - Temperature
- `u`, `v` - Wind components
- `q` - Specific humidity
- `gh` - Geopotential height

## 8. Error Handling

### File Exists Error:
```
FileExistsError: Zarr archive already exists at gs://bucket/output.zarr.
Set overwrite=true to replace it.
```
**Solution:** Set `overwrite: true` in config or use a different output path.

### No GRIB Files Found:
```
ValueError: No GRIB files found at /path/to/grib
```
**Solution:** Check `grib_path` is correct and files exist.

### Variable Not Found:
```
WARNING: Variables not found in GRIB files: ['invalid_var']
```
**Solution:** Check variable names and `filter_by_keys` settings.
