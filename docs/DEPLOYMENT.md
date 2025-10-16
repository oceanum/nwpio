# Deployment Guide

## Prerequisites

- Python 3.9 or higher
- Google Cloud Platform account with GCS access
- GRIB support (eccodes library)
- Sufficient GCS storage quota

## Installation

### Local Development

```bash
# Clone the repository
git clone <repository-url>
cd nwp-download

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Verify installation
nwp-download --version
```

### Production Installation

```bash
pip install nwp-download
```

## Google Cloud Setup

### 1. Create GCS Buckets

```bash
# Create destination bucket for GRIB files
gsutil mb -l us-central1 gs://your-nwp-data-bucket

# Create bucket for Zarr archives
gsutil mb -l us-central1 gs://your-nwp-zarr-bucket
```

### 2. Service Account Setup

```bash
# Create service account
gcloud iam service-accounts create nwp-download \
    --display-name="NWP Download Service Account"

# Grant storage permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:nwp-download@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"

# Create and download key
gcloud iam service-accounts keys create nwp-download-key.json \
    --iam-account=nwp-download@YOUR_PROJECT_ID.iam.gserviceaccount.com

# Set environment variable
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/nwp-download-key.json
```

### 3. Configure Access to Public Data

Ensure your service account has read access to public NWP data buckets:

```bash
# For GFS data (example - adjust based on actual bucket)
gsutil iam ch serviceAccount:nwp-download@YOUR_PROJECT_ID.iam.gserviceaccount.com:objectViewer \
    gs://gcp-public-data-arco-era5
```

## Configuration

### Create Configuration File

```bash
# Generate sample configuration
nwp-download init-config --output config.yaml

# Edit configuration
vim config.yaml
```

### Example Configuration

```yaml
download:
  product: gfs
  resolution: 0p25
  forecast_time: "2024-01-01T00:00:00"
  cycle: 00z
  max_lead_time: 120
  source_bucket: gcp-public-data-arco-era5
  destination_bucket: your-nwp-data-bucket
  destination_prefix: gfs/

process:
  grib_path: gs://your-nwp-data-bucket/gfs/
  variables:
    - t2m
    - u10
    - v10
    - tp
  output_path: gs://your-nwp-zarr-bucket/forecast.zarr
  compression: default

cleanup_grib: false
```

## Running the Application

### Manual Execution

```bash
# Run complete workflow
nwp-download run --config config.yaml

# Download only
nwp-download download \
    --product gfs \
    --resolution 0p25 \
    --time 2024-01-01T00:00:00 \
    --cycle 00z \
    --max-lead-time 120 \
    --source-bucket gcp-public-data-arco-era5 \
    --dest-bucket your-nwp-data-bucket

# Process only
nwp-download process \
    --grib-path gs://your-nwp-data-bucket/gfs/ \
    --variables t2m,u10,v10,tp \
    --output gs://your-nwp-zarr-bucket/forecast.zarr
```

### Dry Run

```bash
# Preview downloads without executing
nwp-download download \
    --product gfs \
    --resolution 0p25 \
    --time 2024-01-01T00:00:00 \
    --cycle 00z \
    --max-lead-time 120 \
    --source-bucket gcp-public-data-arco-era5 \
    --dest-bucket your-nwp-data-bucket \
    --dry-run
```

## Automated Deployment

### Cron Job (Linux/Unix)

```bash
# Edit crontab
crontab -e

# Add entry to run every 6 hours
0 */6 * * * /path/to/venv/bin/nwp-download run --config /path/to/config.yaml >> /var/log/nwp-download.log 2>&1
```

Or use the provided script:

```bash
# Make script executable
chmod +x examples/cron_job.sh

# Edit script with your paths
vim examples/cron_job.sh

# Add to crontab
0 */6 * * * /path/to/examples/cron_job.sh
```

### Docker Deployment

```bash
# Build Docker image
docker build -t nwp-download:latest .

# Run container
docker run \
    -v /path/to/config.yaml:/config/config.yaml \
    -v /path/to/credentials.json:/credentials.json \
    -e GOOGLE_APPLICATION_CREDENTIALS=/credentials.json \
    nwp-download:latest run --config /config/config.yaml
```

### Kubernetes Deployment

```bash
# Create namespace
kubectl create namespace nwp-download

# Create secret for GCS credentials
kubectl create secret generic gcs-key \
    --from-file=key.json=/path/to/nwp-download-key.json \
    -n nwp-download

# Apply configuration
kubectl apply -f examples/kubernetes_cronjob.yaml -n nwp-download

# Check status
kubectl get cronjobs -n nwp-download
kubectl get jobs -n nwp-download
kubectl logs -l job-name=nwp-download-xxxxx -n nwp-download
```

### Google Cloud Run (Scheduled)

```bash
# Build and push image
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/nwp-download

# Deploy Cloud Run job
gcloud run jobs create nwp-download \
    --image gcr.io/YOUR_PROJECT_ID/nwp-download \
    --service-account nwp-download@YOUR_PROJECT_ID.iam.gserviceaccount.com \
    --memory 4Gi \
    --cpu 2 \
    --max-retries 3 \
    --region us-central1

# Create Cloud Scheduler job
gcloud scheduler jobs create http nwp-download-scheduler \
    --location us-central1 \
    --schedule="0 */6 * * *" \
    --uri="https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/YOUR_PROJECT_ID/jobs/nwp-download:run" \
    --http-method POST \
    --oauth-service-account-email nwp-download@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

## Monitoring and Logging

### View Logs

```bash
# Local logs
tail -f /var/log/nwp-download.log

# Kubernetes logs
kubectl logs -f -l app=nwp-download -n nwp-download

# GCP Cloud Logging
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=nwp-download" \
    --limit 50 \
    --format json
```

### Set Up Alerts

Create alerting policies in GCP for:
- Job failures
- Excessive runtime
- Storage quota exceeded
- API errors

## Troubleshooting

### Common Issues

#### 1. Authentication Errors

```bash
# Verify credentials
gcloud auth application-default login

# Check service account permissions
gcloud projects get-iam-policy YOUR_PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:nwp-download@*"
```

#### 2. GRIB File Not Found

- Verify source bucket and path
- Check if data is available for requested date/time
- Ensure read permissions on source bucket

#### 3. Out of Memory

- Reduce chunk sizes in process configuration
- Increase container memory limits
- Process fewer variables at once

#### 4. Slow Downloads

- Increase max_workers parameter
- Ensure good network connectivity
- Consider regional bucket placement

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
nwp-download run --config config.yaml
```

## Performance Tuning

### Download Optimization

- Increase `max_workers` for faster parallel downloads (default: 10)
- Use regional buckets close to data source
- Enable overwrite only when necessary

### Processing Optimization

- Optimize chunk sizes based on access patterns
- Use appropriate compression (zstd for balance, lz4 for speed)
- Process variables in batches if memory constrained

### Cost Optimization

- Use lifecycle policies to archive old data
- Enable cleanup_grib to remove intermediate files
- Use Nearline/Coldline storage for archival data

## Backup and Recovery

### Backup Configuration

```bash
# Backup configuration files
gsutil cp config.yaml gs://your-backup-bucket/configs/

# Backup Zarr archives
gsutil -m rsync -r gs://your-nwp-zarr-bucket gs://your-backup-bucket/zarr/
```

### Disaster Recovery

1. Restore configuration from backup
2. Re-run download for missing data
3. Verify data integrity
4. Resume normal operations

## Security Best Practices

1. **Never commit credentials** to version control
2. **Use service accounts** with minimal required permissions
3. **Enable VPC Service Controls** for sensitive projects
4. **Rotate credentials** regularly
5. **Enable audit logging** for compliance
6. **Use private GCS buckets** for sensitive data
7. **Implement network policies** in Kubernetes

## Scaling

### Horizontal Scaling

- Run multiple instances for different products/cycles
- Use separate configurations for each instance
- Coordinate with distributed locking if needed

### Vertical Scaling

- Increase memory for processing large datasets
- Add more CPU cores for faster compression
- Use high-bandwidth network connections

## Maintenance

### Regular Tasks

- Monitor storage usage and costs
- Review and update configurations
- Check for library updates
- Verify data quality
- Clean up old logs and temporary files

### Updates

```bash
# Update library
pip install --upgrade nwp-download

# Update dependencies
pip install --upgrade -r requirements.txt

# Rebuild Docker image
docker build -t nwp-download:latest .
```
