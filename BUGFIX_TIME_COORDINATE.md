# Bug Fix: Time Coordinate Issue

## Problem

After downloading and processing ECMWF data, all time values in the Zarr output were identical:

```python
dset.time.values
# array(['2025-10-16T00:00:00.000000000', '2025-10-16T00:00:00.000000000',
#        '2025-10-16T00:00:00.000000000'], dtype='datetime64[ns]')
```

All times showed the cycle time (00:00) instead of the forecast valid times (00:00, 03:00, 06:00, etc.).

## Root Cause

GRIB files contain two time coordinates:
- **`time`**: Forecast reference time (cycle time) - constant for all lead times
- **`valid_time`**: Forecast valid time (cycle time + lead time) - what we actually want

The processor was using `time` instead of `valid_time` as the time dimension.

## Solution

Updated `nwpio/processor.py` in the `_load_grib_file()` method to:

1. **Prioritize `valid_time`**: Check for `valid_time` coordinate first
2. **Drop reference time**: Remove the `time` coordinate (cycle time) if it exists
3. **Rename to `time`**: Rename `valid_time` → `time` for consistency with output expectations

### Code Changes

```python
# Before (incorrect)
if "time" not in ds.dims:
    if "valid_time" in ds.coords and "time" not in ds.coords:
        ds = ds.rename({"valid_time": "time"})
    # ... other logic

# After (correct)
if "valid_time" in ds.coords:
    # Drop the reference time coordinate first
    if "time" in ds.coords and "time" not in ds.dims:
        ds = ds.drop_vars("time")
    
    # Use valid_time as the time dimension
    if "valid_time" not in ds.dims:
        ds = ds.expand_dims("valid_time")
    
    # Rename to 'time' for consistency
    ds = ds.rename({"valid_time": "time"})
```

## Expected Result

After this fix, the time coordinate should show the correct forecast valid times:

```python
dset.time.values
# array(['2025-10-16T00:00:00.000000000',  # 0h forecast
#        '2025-10-16T03:00:00.000000000',  # 3h forecast
#        '2025-10-16T06:00:00.000000000'], # 6h forecast
#        dtype='datetime64[ns]')
```

## Testing

To verify the fix:

```bash
# Re-run the processing
nwpio run --config examples/config-ecmwf-wind10m.yaml \
    --cycle 2025-10-16T00:00:00 \
    --max-workers 4

# Check the output
python -c "
import xarray as xr
ds = xr.open_zarr('gs://oceanum-data-dev/forecast/ecmwf_0p25_wind10m_20251016_00z.zarr')
print('Time values:', ds.time.values)
print('Expected: 00:00, 03:00, 06:00 for 3-hourly data')
"
```

## Impact

- **Affected**: All GRIB-based processing (ECMWF, GFS if they have valid_time)
- **Severity**: High - time coordinate is fundamental for forecast data
- **Backward compatibility**: Maintained - only affects how time is extracted from GRIB

## Related Files

- `nwpio/processor.py` - GRIB loading logic
- All config files using GRIB data sources
