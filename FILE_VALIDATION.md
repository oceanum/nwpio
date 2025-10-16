# File Availability Validation

## Overview

Before downloading GRIB files, NWPIO validates that all required files are available in the source bucket. This is **critical for production workflows** where NWP models may still be processing a forecast cycle.

## The Problem

When downloading forecast data in real-time:

1. **Incomplete cycles**: The NWP model may still be processing some lead times
2. **Partial uploads**: The last file may be in the process of uploading (uploads aren't atomic)
3. **Wasted resources**: Starting a download that will fail wastes time and compute costs

## The Solution: Fail Fast

NWPIO validates file availability using a **"next file" strategy** and **fails immediately** if files are missing:

1. ✅ Check all required files exist (0h to max_lead_time)
2. ✅ Check the **next lead time file** also exists
3. ✅ Raise `FileNotFoundError` with detailed diagnostics if any files are missing
4. ✅ Your orchestration system can retry the task later

### Why Fail Fast?

**For automated workflows:**
- ❌ Don't waste time and resources waiting
- ✅ Fail immediately with clear error messages
- ✅ Let your orchestration system handle retries
- ✅ Check happens before any downloads start

### Why Check the Next File?

If you request `max_lead_time: 120`, NWPIO will:
- Check files for lead times: 0, 1, 2, ..., 120 (121 files)
- **Also check lead time 121** (the next hourly file)

If lead time 121 exists, we know lead time 120 must be fully uploaded (not mid-upload).

## Configuration

### Enable Validation (Default - Recommended)

```yaml
download:
  validate_before_download: true  # Default: true
```

**Behavior:**
- ✅ Checks all files exist before downloading
- ✅ Fails immediately with detailed error if any files are missing
- ✅ Shows which lead times are available vs missing
- ✅ Perfect for automated workflows with retry logic

**Error Output Example:**
```
================================================================================
GRIB FILES NOT READY - Forecast cycle incomplete
================================================================================
Product: gfs
Cycle: 2024-01-15 06:00:00 UTC
Resolution: 0p25
Requested lead time: 0-120h

Status:
  ✓ Available: 95 files
  ✗ Missing: 27 files

Missing required lead times (26):
  [95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, ...]

Available lead times (95):
  [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, ...]

Validation file missing:
  Lead time 121h not yet available
  (This ensures lead time 120h is fully uploaded)

Action:
  The forecast cycle is still processing. This task will be retried.
  Typical GFS processing time: 3-4 hours after cycle start
================================================================================
```

### Skip Validation (Not Recommended)

```yaml
download:
  validate_before_download: false
```

**Behavior:**
- No validation, starts downloading immediately
- Download will fail partway through if files are missing
- Only use for: Testing, or when you're certain files exist

## Examples

### Example 1: GFS 0.25° with 120h Lead Time

```yaml
download:
  product: gfs
  resolution: 0p25
  cycle: '2024-01-15T00:00:00'
  max_lead_time: 120
  validate_before_download: true
```

**Validation checks:**
- Required: 0-120h hourly (121 files)
- Validation: 121h (next hourly file)
- **Total checked: 122 files**

### Example 2: ECMWF ENS with 160h Lead Time

```yaml
download:
  product: ecmwf-ens
  cycle: '2024-01-15T00:00:00'
  max_lead_time: 160
  validate_before_download: true
```

**Validation checks:**
- Required: 0-144h 3-hourly + 150-156h 6-hourly (51 files)
- Validation: 162h (next 6-hourly file)
- **Total checked: 52 files**

### Example 3: Full GFS Forecast

```yaml
download:
  product: gfs
  resolution: 0p25
  cycle: '2024-01-15T06:00:00'
  max_lead_time: 384
  source_bucket: global-forecast-system
  validate_before_download: true
```

**Validation checks:**
- Required: 0-120h hourly + 123-240h 3-hourly + 252-384h 12-hourly
- Validation: Next file after 384h
- Ensures complete forecast is available

## Lead Time Intervals

The validation logic understands variable intervals for each model:

### GFS
```
0-120h:   1h intervals  → Next: 121h
120-240h: 3h intervals  → Next: 123h, 126h, etc.
240-384h: 12h intervals → Next: 252h, 264h, etc.
```

### ECMWF HRES
```
0-90h:    1h intervals → Next: 91h
90-240h:  3h intervals → Next: 93h, 96h, etc.
```

### ECMWF ENS
```
0-144h:   3h intervals → Next: 147h
144-360h: 6h intervals → Next: 150h, 156h, etc.
```

## Error Messages

### When Files Are Missing

The validation raises `FileNotFoundError` with detailed diagnostics (see example at top of document).

**Exit code:** 1 (can be used by orchestration systems for retry logic)

### When Files Are Available

```
INFO - ✓ All 121 required files available (validated with lead time 121h)
INFO - Found 121 files to download
Downloading GRIB files: 100%|██████████| 121/121 [02:15<00:00]
```

**Exit code:** 0 (success)

## Implementation Details

### Validation Flow

```python
# 1. Generate list of required files
file_specs = data_source.get_file_list()  # 0 to max_lead_time

# 2. Get next lead time for validation
next_lead_time = data_source.get_next_lead_time()  # max_lead_time + interval

# 3. Create validation spec for next file
validation_specs = file_specs + [next_file_spec]

# 4. Check all files exist
for spec in validation_specs:
    if not fs.exists(spec.source_path):
        missing_files.append(spec)

# 5. Wait or fail based on configuration
if missing_files and wait_for_files:
    time.sleep(30)  # Check again in 30 seconds
elif missing_files:
    raise Error("Files missing")
```

### Next Lead Time Calculation

Each data source implements `get_next_lead_time()`:

```python
# GFS example
def get_next_lead_time(self) -> int:
    if 0 <= max_lead_time < 120:
        return max_lead_time + 1  # Hourly
    elif 120 <= max_lead_time < 240:
        return max_lead_time + 3  # 3-hourly
    elif 240 <= max_lead_time < 384:
        return max_lead_time + 12  # 12-hourly
```

## Best Practices

1. **Always enable validation** for production workflows (`validate_before_download: true`)
2. **Check logs** for detailed diagnostics when validation fails
3. **Use retry logic** in your orchestration system to handle incomplete cycles
4. **Monitor forecast processing times** - GFS typically takes 3-4 hours after cycle start
