# Environment Variables and CLI Arguments

NWPIO supports multiple ways to set the forecast cycle and other parameters, with a clear precedence order.

## Precedence Order (Highest to Lowest)

1. **CLI arguments** (`--cycle`)
2. **Environment variables** (`$CYCLE`)
3. **Config file** (default value)

## Setting the Cycle

### Method 1: CLI Argument (Highest Priority)

```bash
nwpio run --config config.yaml --cycle "2025-10-15T12:00:00"
```

### Method 2: Environment Variable

```bash
export CYCLE="2025-10-15T00:00:00"
nwpio run --config config.yaml
```

Or inline:

```bash
CYCLE="2025-10-15T00:00:00" nwpio run --config config.yaml
```

### Method 3: Config File (Default)

```yaml
download:
  cycle: '2025-10-15T00:00:00'  # Used if no CLI arg or env var
```

### In Scripts

```bash
#!/bin/bash
set -e

# Calculate current cycle (round down to nearest 6 hours)
HOUR=$(date -u +%H)
CYCLE_HOUR=$((HOUR / 6 * 6))
export CYCLE=$(date -u +%Y-%m-%d)T$(printf '%02d' $CYCLE_HOUR):00:00

echo "Processing cycle: $CYCLE"
nwpio run --config config-production.yaml --max-workers 16
```

## Common Variables

### CYCLE (Required for most workflows)

Forecast initialization time in ISO 8601 format:

```bash
export CYCLE="2025-10-15T00:00:00"
export CYCLE="2025-10-15T06:00:00"
export CYCLE="2025-10-15T12:00:00"
export CYCLE="2025-10-15T18:00:00"
```

**Used in:**
- `download.cycle` - Determines which forecast to download
- `{cycle:...}` placeholders in paths - For dynamic path formatting

### MAX_LEAD_TIME

Maximum forecast lead time in hours:

```bash
export MAX_LEAD_TIME="120"  # 5 days
export MAX_LEAD_TIME="240"  # 10 days
export MAX_LEAD_TIME="384"  # 16 days (full GFS)
```

### OUTPUT_BUCKET

GCS bucket for output Zarr archives:

```bash
export OUTPUT_BUCKET="oceanum-data-prod"
```

```yaml
process:
  - output_path: gs://${OUTPUT_BUCKET}/forecast/wind_{cycle:%Y%m%d}.zarr
```

## Example Production Config

```yaml
# config-production.yaml
cleanup_grib: false

download:
  cycle: ${CYCLE}  # From environment
  destination_bucket: null
  local_download_dir: /tmp/nwp-data
  max_lead_time: ${MAX_LEAD_TIME:-240}  # Default: 240 if not set
  product: gfs
  resolution: 0p25
  source_bucket: global-forecast-system
  validate_before_download: true

process:
  - filter_by_keys:
      typeOfLevel: heightAboveGround
      level: 10
    grib_path: /tmp/nwp-data/gfs/0p25/{cycle:%Y%m%d}/{cycle:%H}/
    output_path: gs://${OUTPUT_BUCKET}/forecast/gfs_wind10m_{cycle:%Y%m%d}_{cycle:%Hz}.zarr
    overwrite: true
    write_local_first: true
    max_upload_workers: 16
    chunks: {time: -1, longitude: 128, latitude: 128}
    variables: [u10, v10]
```

**Run with:**

```bash
export CYCLE="2025-10-15T00:00:00"
export MAX_LEAD_TIME="240"
export OUTPUT_BUCKET="oceanum-data-prod"
nwpio run --config config-production.yaml --max-workers 16
```

## Error Handling

If a required environment variable is not set, NWPIO will fail immediately with a clear error:

```
ERROR - Workflow failed: Environment variable 'CYCLE' not found. Please set it before running.
```

This ensures you catch configuration errors early, before any downloads start.

## Default Values (Not Supported)

Currently, NWPIO does not support default values in the config file (e.g., `${VAR:-default}`). 

**Workaround:** Set defaults in your script:

```bash
#!/bin/bash
export CYCLE="${CYCLE:-$(date -u +%Y-%m-%dT%H:00:00)}"
export MAX_LEAD_TIME="${MAX_LEAD_TIME:-240}"
nwpio run --config config.yaml
```

## Best Practices

1. **Always set CYCLE** - This is the most critical variable
2. **Validate before running** - Check that required variables are set:
   ```bash
   if [ -z "$CYCLE" ]; then
       echo "ERROR: CYCLE not set"
       exit 1
   fi
   ```
3. **Use ISO 8601 format** - Always use `YYYY-MM-DDTHH:MM:SS` for dates
4. **Document required variables** - Add comments to your config showing what's needed
5. **Log the values** - Echo variables before running for debugging:
   ```bash
   echo "CYCLE=$CYCLE"
   echo "MAX_LEAD_TIME=$MAX_LEAD_TIME"
   nwpio run --config config.yaml
   ```

## Integration Examples

### Cron Job

```bash
#!/bin/bash
# /usr/local/bin/gfs-download.sh
set -e

# Calculate current cycle
HOUR=$(date -u +%H)
CYCLE_HOUR=$((HOUR / 6 * 6))
export CYCLE=$(date -u +%Y-%m-%d)T$(printf '%02d' $CYCLE_HOUR):00:00

# Run NWPIO
cd /opt/nwpio
nwpio run --config config-production.yaml --max-workers 16
```

**Crontab:**
```
30 0,6,12,18 * * * /usr/local/bin/gfs-download.sh >> /var/log/gfs-download.log 2>&1
```

### Kubernetes CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: gfs-processor
spec:
  schedule: "30 0,6,12,18 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: nwpio
            image: nwpio:latest
            command:
            - /bin/bash
            - -c
            - |
              # Calculate cycle
              HOUR=$(date -u +%H)
              CYCLE_HOUR=$((HOUR / 6 * 6))
              export CYCLE=$(date -u +%Y-%m-%d)T$(printf '%02d' $CYCLE_HOUR):00:00
              
              echo "Processing cycle: $CYCLE"
              nwpio run --config /config/config-production.yaml --max-workers 16
            env:
            - name: OUTPUT_BUCKET
              value: "oceanum-data-prod"
            - name: MAX_LEAD_TIME
              value: "240"
```

### Argo Workflows

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  name: gfs-processor
spec:
  entrypoint: process-gfs
  arguments:
    parameters:
    - name: cycle
      value: "2025-10-15T00:00:00"
  
  templates:
  - name: process-gfs
    inputs:
      parameters:
      - name: cycle
    container:
      image: nwpio:latest
      command: [nwpio, run, --config, /config/config-production.yaml, --max-workers, "16"]
      env:
      - name: CYCLE
        value: "{{inputs.parameters.cycle}}"
      - name: MAX_LEAD_TIME
        value: "240"
      - name: OUTPUT_BUCKET
        value: "oceanum-data-prod"
```

## Summary

Environment variable substitution makes NWPIO configs:
- ✅ **Reusable** - Same config for different cycles
- ✅ **Flexible** - Easy to parameterize
- ✅ **Safe** - Fails fast if variables missing
- ✅ **Scriptable** - Works well with automation
