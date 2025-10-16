# Getting Started with NWP Download

This guide will help you get started with downloading and processing NWP forecast data.

## Installation

### Step 1: Install the Library

```bash
cd /source/nwp-download
pip install -e .
```

### Step 2: Install System Dependencies

The library requires eccodes for GRIB support:

**Ubuntu/Debian:**
```bash
sudo apt-get install libeccodes-dev libeccodes-tools
```

**macOS:**
```bash
brew install eccodes
```

**Docker:**
```bash
# Use the provided Dockerfile which includes all dependencies
docker build -t nwp-download .
```

### Step 3: Set Up Google Cloud Authentication

```bash
# Option 1: User authentication (development)
gcloud auth application-default login

# Option 2: Service account (production)
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

## Your First Download

### Using the CLI

```bash
# 1. Create a sample configuration
nwp-download init-config --output my-config.yaml

# 2. Edit the configuration with your GCS bucket names
# Change "your-bucket-name" to your actual bucket

# 3. Preview what will be downloaded (dry run)
nwp-download download \
    --product gfs \
    --resolution 0p25 \
    --time 2024-01-01T00:00:00 \
    --cycle 00z \
    --max-lead-time 24 \
    --source-bucket gcp-public-data-arco-era5 \
    --dest-bucket YOUR-BUCKET-NAME \
    --dry-run

# 4. Run the actual download (start small!)
nwp-download download \
    --product gfs \
    --resolution 0p25 \
    --time 2024-01-01T00:00:00 \
    --cycle 00z \
    --max-lead-time 24 \
    --source-bucket gcp-public-data-arco-era5 \
    --dest-bucket YOUR-BUCKET-NAME
```

### Using Python

```python
from datetime import datetime
from nwp_download import GribDownloader, DownloadConfig

# Configure download
config = DownloadConfig(
    product="gfs",
    resolution="0p25",
    forecast_time=datetime(2024, 1, 1, 0),
    cycle="00z",
    max_lead_time=24,  # Start small!
    source_bucket="gcp-public-data-arco-era5",
    destination_bucket="YOUR-BUCKET-NAME",
)

# Download files
downloader = GribDownloader(config, max_workers=5)
files = downloader.download()

print(f"Downloaded {len(files)} files")
```

## Your First Processing Job

### Using the CLI

```bash
# 1. Inspect GRIB files to see available variables
nwp-download process \
    --grib-path gs://YOUR-BUCKET-NAME/gfs/ \
    --variables t2m \
    --output /tmp/test.zarr \
    --inspect

# 2. Process to Zarr
nwp-download process \
    --grib-path gs://YOUR-BUCKET-NAME/gfs/ \
    --variables t2m,u10,v10 \
    --output gs://YOUR-BUCKET-NAME/output.zarr
```

### Using Python

```python
from nwp_download import GribProcessor, ProcessConfig

# Configure processing
config = ProcessConfig(
    grib_path="gs://YOUR-BUCKET-NAME/gfs/",
    variables=["t2m", "u10", "v10"],
    output_path="gs://YOUR-BUCKET-NAME/output.zarr",
    chunks={"time": 1, "latitude": 100, "longitude": 100},
)

# Process files
processor = GribProcessor(config)
output = processor.process()

print(f"Created Zarr archive: {output}")
```

## Complete Workflow

### Using Configuration File

```bash
# 1. Create and edit config
nwp-download init-config --output workflow.yaml
vim workflow.yaml  # Edit with your settings

# 2. Run complete workflow
nwp-download run --config workflow.yaml
```

### Using Python

```python
from datetime import datetime
from nwp_download import (
    GribDownloader, GribProcessor,
    DownloadConfig, ProcessConfig
)

# Step 1: Download
download_config = DownloadConfig(
    product="gfs",
    resolution="0p25",
    forecast_time=datetime(2024, 1, 1, 0),
    cycle="00z",
    max_lead_time=120,
    source_bucket="gcp-public-data-arco-era5",
    destination_bucket="YOUR-BUCKET-NAME",
    destination_prefix="nwp-data/",
)

downloader = GribDownloader(download_config)
files = downloader.download()
print(f"Downloaded {len(files)} files")

# Step 2: Process
process_config = ProcessConfig(
    grib_path="gs://YOUR-BUCKET-NAME/nwp-data/",
    variables=["t2m", "u10", "v10", "tp"],
    output_path="gs://YOUR-BUCKET-NAME/forecast.zarr",
)

processor = GribProcessor(process_config)
output = processor.process()
print(f"Created: {output}")
```

## Reading the Output

Once you've created a Zarr archive, you can read it with xarray:

```python
import xarray as xr

# Open Zarr archive
ds = xr.open_zarr("gs://YOUR-BUCKET-NAME/forecast.zarr")

# Explore the data
print(ds)
print(ds.variables)

# Select specific data
t2m = ds['t2m']
print(t2m)

# Select by time
first_timestep = ds.isel(time=0)
print(first_timestep)

# Plot (requires matplotlib)
import matplotlib.pyplot as plt
ds['t2m'].isel(time=0).plot()
plt.show()
```

## Setting Up Automated Downloads

### Daily Cron Job

```bash
# Edit crontab
crontab -e

# Add entry to run daily at 1 AM
0 1 * * * /path/to/venv/bin/nwp-download run --config /path/to/config.yaml >> /var/log/nwp.log 2>&1
```

### Kubernetes CronJob

```bash
# 1. Create GCS credentials secret
kubectl create secret generic gcs-key \
    --from-file=key.json=/path/to/credentials.json

# 2. Edit and apply the CronJob manifest
vim examples/kubernetes_cronjob.yaml
kubectl apply -f examples/kubernetes_cronjob.yaml

# 3. Monitor
kubectl get cronjobs
kubectl get jobs
kubectl logs -l job-name=nwp-download-xxxxx
```

## Common Patterns

### Download Latest Forecast

```python
from datetime import datetime, timedelta

# Get most recent 00z cycle
now = datetime.utcnow()
forecast_time = now.replace(hour=0, minute=0, second=0, microsecond=0)

config = DownloadConfig(
    product="gfs",
    resolution="0p25",
    forecast_time=forecast_time,
    cycle="00z",
    max_lead_time=120,
    source_bucket="gcp-public-data-arco-era5",
    destination_bucket="YOUR-BUCKET-NAME",
)
```

### Process Multiple Cycles

```python
from datetime import datetime, timedelta

cycles = ["00z", "06z", "12z", "18z"]
base_date = datetime(2024, 1, 1)

for cycle in cycles:
    hour = int(cycle.replace("z", ""))
    forecast_time = base_date.replace(hour=hour)
    
    # Download and process each cycle
    # ... (use the patterns above)
```

### Extract Specific Pressure Levels

```python
config = ProcessConfig(
    grib_path="gs://YOUR-BUCKET-NAME/gfs/",
    variables=["t", "u", "v"],  # Temperature and wind
    output_path="gs://YOUR-BUCKET-NAME/500hPa.zarr",
    filter_by_keys={
        "typeOfLevel": "isobaricInhPa",
        "level": 500,  # 500 hPa level
    },
)
```

## Troubleshooting

### Issue: "Authentication failed"

**Solution:**
```bash
# Re-authenticate
gcloud auth application-default login

# Or check service account key
echo $GOOGLE_APPLICATION_CREDENTIALS
```

### Issue: "Source file not found"

**Possible causes:**
1. Data not yet available for requested date/time
2. Incorrect source bucket or path
3. No read permissions on source bucket

**Solution:**
- Verify the date/time is in the past
- Check source bucket name
- Ensure you have read access

### Issue: "Out of memory"

**Solution:**
```python
# Reduce chunk sizes
config = ProcessConfig(
    # ... other settings ...
    chunks={"time": 1, "latitude": 50, "longitude": 50},  # Smaller chunks
)

# Or process fewer variables at once
```

### Issue: "Variable not found in GRIB"

**Solution:**
```bash
# First inspect to see available variables
nwp-download process \
    --grib-path gs://YOUR-BUCKET-NAME/gfs/ \
    --variables t2m \
    --output /tmp/test.zarr \
    --inspect
```

## Next Steps

1. **Read the full documentation**: [README.md](README.md)
2. **Explore examples**: [examples/](examples/)
3. **API reference**: [docs/API.md](docs/API.md)
4. **Production deployment**: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
5. **Architecture details**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Tips for Success

1. **Start small**: Test with short lead times (24h) before full forecasts
2. **Use dry-run**: Always preview downloads first
3. **Monitor costs**: GCS storage and egress can add up
4. **Optimize chunks**: Tune chunking for your access patterns
5. **Enable logging**: Use logs to debug issues
6. **Verify downloads**: Check that files exist before processing

## Getting Help

- Check the documentation in `docs/`
- Review examples in `examples/`
- Look at test files in `tests/`
- Open an issue if you find bugs

Happy forecasting! 🌤️
