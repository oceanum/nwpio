# NWPIO Workflow Summary

## Multi-Process Workflow Architecture

The new workflow supports **downloading GRIB files once** and **processing them multiple times** with different configurations. This is ideal for cloud/cluster environments where you want to:

1. Download GRIB files from cloud storage to local disk
2. Extract multiple variable sets into separate Zarr archives
3. Upload all Zarr archives to cloud storage
4. Clean up GRIB files (optional)

## Key Benefits

✅ **Download once, process many times** - No need to re-download or re-upload GRIB files  
✅ **Fast local processing** - All processing happens on local files (4-5 seconds per file)  
✅ **Parallel uploads** - 8x faster uploads with 16 parallel workers (~26 seconds for 51 files)  
✅ **Automatic cleanup** - Optional GRIB file deletion after all processing is complete  
✅ **Flexible configuration** - Support for multiple variable sets, levels, and output paths

## Performance Metrics

From testing with GFS 0.25° data (7 forecast hours):

- **Download**: ~5 seconds (8 workers, parallel download)
- **GRIB loading**: ~4 seconds per process (7 files, local disk)
- **Zarr upload**: ~20-26 seconds (16 workers, parallel upload)
- **Total for 2 processes**: ~45 seconds (vs 3+ minutes with old approach)

## Configuration Structure

```yaml
cleanup_grib: true  # Delete GRIB files after all processing

download:
  cycle: '2024-01-01T00:00:00'
  product: gfs
  resolution: 0p25
  max_lead_time: 6
  # ... other download config

process:  # List of process configurations
  - # Process 1: 10m winds
    filter_by_keys:
      typeOfLevel: heightAboveGround
      level: 10
    grib_path: /local/path/  # Optional, auto-set from download
    output_path: gs://bucket/wind_{cycle:%Y%m%d}.zarr
    variables: [u10, v10]
    
  - # Process 2: 2m temperature
    filter_by_keys:
      typeOfLevel: heightAboveGround
      level: 2
    output_path: gs://bucket/temp_{cycle:%Y%m%d}.zarr
    variables: [t2m, d2m]
```

## Features Implemented

### 1. Cycle-Based Path Formatting
Both `grib_path` and `output_path` support Python datetime formatting:
- `{cycle:%Y%m%d}` → `20240101`
- `{cycle:%H}` → `00`
- `{cycle:%Hz}` → `00z`
- `{cycle:%Y-%m-%d_%H%M}` → `2024-01-01_0000`

### 2. Parallel Downloads
- Configurable worker count (default: 4)
- Progress bar with tqdm
- Error handling and retry logic

### 3. Parallel Uploads
- Configurable worker count (default: 16)
- 8x faster than sequential uploads
- Automatic temp directory cleanup

### 4. GRIB File Discovery
Supports files with and without extensions:
- Standard: `*.grib`, `*.grb`, `*.grib2`
- GFS format: `gfs.t00z.pgrb2.0p25.f000`
- ECMWF format: `ecmwf.*`

### 5. Variable Filtering
Uses cfgrib's `filter_by_keys` for efficient extraction:
```yaml
filter_by_keys:
  typeOfLevel: heightAboveGround
  level: 10
```

## Usage Examples

### Example 1: Download and Process Multiple Variable Sets
```bash
nwpio run --config config-multi.yaml --max-workers 8
```

### Example 2: Process Only (Skip Download)
```bash
nwpio run --config config-multi.yaml --skip-download
```

### Example 3: Download Only (Skip Processing)
```bash
nwpio run --config config-multi.yaml --skip-process
```

## Next Steps / Future Enhancements

1. **Kerchunk support** - Create reference files instead of downloading entire GRIBs
2. **Append mode** - Add new forecast hours to existing Zarr archives
3. **Rechunking** - Optimize chunk sizes for different access patterns
4. **Compression** - Add compression options for Zarr arrays
5. **Metadata** - Preserve more GRIB metadata in Zarr attributes
6. **Validation** - Add data quality checks and validation

## Troubleshooting

### Issue: "No GRIB files found"
- Check that `grib_path` is set correctly
- Verify files exist at the specified path
- Ensure file naming matches expected patterns

### Issue: "Connection pool warnings"
- These are harmless - just indicates efficient connection reuse
- Reduce `max_upload_workers` if you want to eliminate them

### Issue: Slow GRIB loading from cloud
- Always download files first, don't process directly from cloud
- Use the multi-process workflow to download once, process many times
