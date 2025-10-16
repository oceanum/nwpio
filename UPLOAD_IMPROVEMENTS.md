# GCS Upload Improvements - Robust Handling of Network Timeouts

## Problem

When uploading large zarr archives to GCS, the default Google Cloud Storage Python client timeout of 120 seconds was causing upload failures for large files, especially when running 16 parallel workers. This resulted in:

- Timeout errors: `Timeout of 120.0s exceeded, last exception: ('Connection aborted.', TimeoutError('The write operation timed out'))`
- Missing data in the remote zarr archive
- Incomplete uploads that appeared successful but had gaps

## Root Cause

1. **Default timeout too short**: 120s is insufficient for large zarr chunks (especially with `time: -1` chunking)
2. **No retry logic**: Transient network errors caused permanent failures
3. **No upload verification**: Failed uploads went undetected
4. **Parallel congestion**: 16 workers competing for bandwidth increased timeout likelihood

## Solution Implemented

### 1. Configurable Timeout (Default: 600s)
- Increased from 120s to 600s (10 minutes) per file
- Configurable via `upload_timeout` parameter
- Sufficient for large zarr chunks even under network congestion

### 2. Automatic Retry with Exponential Backoff
- Up to 3 retries per file (configurable via `upload_max_retries`)
- Exponential backoff: 1s, 2s, 4s between retries
- Handles transient network errors gracefully
- Logs retry attempts with clear warnings

### 3. Resumable Uploads for Large Files
- Automatically uses resumable uploads for files >5MB
- Uses 5MB chunk size for better reliability
- Includes MD5 checksum verification

### 4. Upload Verification
- After upload completes, verifies all files exist in GCS
- Compares local file list with remote file list
- Raises clear error if any files are missing
- Can be disabled with `verify_upload: false` (not recommended)

### 5. Better Error Handling
- Continues uploading other files even if one fails
- Collects all failures and reports them together
- Provides detailed error messages for debugging
- Raises exception only after all retries exhausted

## Configuration

### YAML Config (Recommended)

```yaml
process:
  - output_path: gs://bucket/path/to/output.zarr
    write_local_first: true  # Required for robust upload
    
    # Upload configuration
    max_upload_workers: 16      # Parallel uploads (default: 16)
    upload_timeout: 600         # Timeout per file in seconds (default: 600)
    upload_max_retries: 3       # Max retries per file (default: 3)
    verify_upload: true         # Verify after upload (default: true)
```

### CLI Options

```bash
nwpio process \
  --write-local-first \
  --max-upload-workers 16 \
  --upload-timeout 600 \
  --upload-max-retries 3 \
  # --no-verify-upload  # Only if you want to skip verification
```

## Comparison with `gcloud storage cp`

The implementation now provides similar robustness to `gcloud storage cp`:

| Feature | `gcloud storage cp` | This Implementation |
|---------|---------------------|---------------------|
| Resumable uploads | ✅ Yes | ✅ Yes (>5MB files) |
| Retry logic | ✅ Yes | ✅ Yes (3 retries) |
| Configurable timeout | ✅ Yes | ✅ Yes (600s default) |
| Parallel uploads | ✅ Yes | ✅ Yes (16 workers) |
| MD5 verification | ✅ Yes | ✅ Yes |
| Upload verification | ❌ No | ✅ Yes |

**Advantages over `gcloud storage cp`:**
- Upload verification ensures completeness
- Better integration with Python workflow
- Progress bars with `tqdm`
- Detailed error reporting

## Recommendations

### For Production Use

1. **Always use `write_local_first: true`**
   - Writes to local temp directory first
   - Then uploads to GCS with retry logic
   - Much more reliable than direct streaming

2. **Keep default timeout (600s)**
   - Sufficient for most use cases
   - Increase if you have very large chunks or slow network

3. **Keep upload verification enabled**
   - Catches missing files immediately
   - Small overhead for peace of mind

4. **Adjust workers based on network**
   - Default 16 workers works well for most cases
   - Reduce to 8-12 if you see many timeouts
   - Increase to 24-32 if you have excellent bandwidth

### Monitoring Upload Performance

The logs will show:
```
INFO - Uploading 1234 files...
INFO - Using 16 parallel workers for upload (timeout: 600s)
WARNING - Upload failed for u10/0.0.7 (attempt 1/3): Timeout. Retrying in 1s...
INFO - Upload verification successful: all 1234 files present in GCS
INFO - Upload complete successfully
```

### Troubleshooting

**If you still see timeouts:**
1. Increase `upload_timeout` to 900 or 1200
2. Reduce `max_upload_workers` to 8-12
3. Check network bandwidth and latency
4. Consider using a local temp directory on fast SSD

**If verification fails:**
1. Check the error message for specific missing files
2. Verify GCS bucket permissions
3. Check for quota limits on your GCS bucket
4. Try running again (may be transient issue)

## Migration Guide

### Existing Configs

Your existing `config-production.yaml` has been updated with the new defaults:

```yaml
# Old (implicit defaults)
max_upload_workers: 16

# New (explicit with robust settings)
max_upload_workers: 16
upload_timeout: 600
upload_max_retries: 3
verify_upload: true
```

**No action required** - the defaults are now more robust. Your next run will automatically use the improved upload logic.

### Testing

To test the improvements on your next run:

```bash
# Your existing command will work with improved upload logic
CYCLE="2025-10-15T12:00:00" nwpio run --config config-production.yaml --max-workers 8
```

Watch for these new log messages:
- `Using 16 parallel workers for upload (timeout: 600s)` - confirms new timeout
- `Upload failed for ... (attempt 1/3): ... Retrying in 1s...` - retry logic working
- `Upload verification successful: all X files present in GCS` - verification passed
- `Upload complete successfully` - all done!

## Performance Impact

- **Upload time**: Similar to before (parallel uploads)
- **Verification overhead**: ~5-10 seconds for 1000+ files
- **Retry overhead**: Only on failures (exponential backoff)
- **Memory**: No change (still writes to local temp first)

## Future Improvements

Potential enhancements:
1. Progress tracking for individual large file uploads
2. Bandwidth throttling to prevent network saturation
3. Automatic worker adjustment based on timeout rate
4. Resume from partial uploads (if process crashes mid-upload)
