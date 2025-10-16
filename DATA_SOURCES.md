# NWP Data Sources

This document provides information about publicly available NWP data sources and their GCS paths.

## Important Note

The exact GCS bucket paths and structures in this library are **examples** and need to be updated based on the actual public data sources you're using. The path patterns in `sources.py` should be adjusted to match your specific data provider.

## Known Public Data Sources

### 1. NOAA GFS Data

**AWS S3 (Public)**
- Bucket: `noaa-gfs-bdp-pds`
- Format: GRIB2
- Path pattern: `gfs.YYYYMMDD/HH/atmos/gfs.tHHz.pgrb2.0p25.fFFF`
- Documentation: https://registry.opendata.aws/noaa-gfs-bdp-pds/

**Google Cloud (via AWS sync)**
- You may need to sync from AWS to your own GCS bucket
- Or use Google's Earth Engine Data Catalog

### 2. ECMWF Open Data

**AWS S3 (Public)**
- Bucket: `ecmwf-forecasts`
- Products: HRES, ENS
- Format: GRIB2
- Documentation: https://registry.opendata.aws/ecmwf-forecasts/

**Direct ECMWF**
- API: https://www.ecmwf.int/en/forecasts/datasets/open-data
- Requires API key for some products

### 3. Google Earth Engine

**Available datasets:**
- NOAA GFS (historical)
- ERA5 (reanalysis, not forecasts)
- Various other weather datasets

**Access:**
- Requires Earth Engine authentication
- Different API than standard GCS

### 4. Copernicus Climate Data Store

**Products:**
- ERA5 reanalysis
- Seasonal forecasts
- Climate projections

**Access:**
- Requires CDS API key
- Download via API, then upload to your GCS

## Setting Up Your Own Data Pipeline

Since public GCS buckets for real-time NWP data are limited, here's how to set up your own:

### Option 1: Sync from AWS to GCS

```bash
# Install AWS CLI and gsutil
pip install awscli

# Sync GFS data from AWS to your GCS bucket
aws s3 sync s3://noaa-gfs-bdp-pds/gfs.20240101/00/ \
    gs://your-bucket/gfs/20240101/00/ \
    --no-sign-request

# Automate with a script
cat > sync_gfs.sh << 'EOF'
#!/bin/bash
DATE=$(date -u +%Y%m%d)
CYCLE="00"
aws s3 sync s3://noaa-gfs-bdp-pds/gfs.${DATE}/${CYCLE}/ \
    gs://your-bucket/gfs/${DATE}/${CYCLE}/ \
    --no-sign-request
EOF

chmod +x sync_gfs.sh
```

### Option 2: Download from NOAA and Upload to GCS

```bash
# Download from NOAA NOMADS
wget https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/gfs.20240101/00/atmos/gfs.t00z.pgrb2.0p25.f000

# Upload to GCS
gsutil cp gfs.t00z.pgrb2.0p25.f000 gs://your-bucket/gfs/20240101/00/
```

### Option 3: Use ECMWF Open Data API

```python
import requests
from google.cloud import storage

def download_ecmwf_to_gcs(date, time, step, bucket_name):
    """Download ECMWF open data and upload to GCS."""
    
    # ECMWF Open Data API
    url = f"https://data.ecmwf.int/forecasts/{date}/{time}z/0p25-oper/{step}h/..."
    
    # Download
    response = requests.get(url)
    
    # Upload to GCS
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(f"ecmwf/{date}/{time}/step{step}.grib")
    blob.upload_from_string(response.content)
```

## Updating the Library for Your Data Source

Once you have your data in GCS, update the path patterns in `nwpio/sources.py`:

### For GFS

```python
class GFSSource(DataSource):
    def get_file_list(self) -> List[GribFileSpec]:
        # Update this pattern to match your GCS structure
        source_path = (
            f"gs://{self.source_bucket}/gfs/{date_str}/{cycle_str}/"
            f"gfs.t{cycle_str}z.pgrb2.{self.resolution}.f{lead_str}"
        )
        # ... rest of the code
```

### For ECMWF

```python
class ECMWFSource(DataSource):
    def get_file_list(self) -> List[GribFileSpec]:
        # Update this pattern to match your GCS structure
        source_path = (
            f"gs://{self.source_bucket}/ecmwf/{date_str}/{cycle_str}/"
            f"ecmwf.{cycle_str}z.{self.resolution}.f{lead_str}.grib"
        )
        # ... rest of the code
```

## Example: Complete Data Pipeline

Here's a complete example of setting up a data pipeline:

```bash
#!/bin/bash
# complete_pipeline.sh - Download from NOAA, upload to GCS, process to Zarr

set -e

DATE=$(date -u +%Y%m%d)
CYCLE="00"
BUCKET="your-bucket-name"

echo "=== Step 1: Download from NOAA ==="
for hour in $(seq -f "%03g" 0 3 120); do
    FILE="gfs.t${CYCLE}z.pgrb2.0p25.f${hour}"
    URL="https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/gfs.${DATE}/${CYCLE}/atmos/${FILE}"
    
    echo "Downloading ${FILE}..."
    wget -q ${URL} -O /tmp/${FILE}
    
    echo "Uploading to GCS..."
    gsutil cp /tmp/${FILE} gs://${BUCKET}/gfs/${DATE}/${CYCLE}/
    
    rm /tmp/${FILE}
done

echo "=== Step 2: Process to Zarr ==="
nwpio process \
    --grib-path gs://${BUCKET}/gfs/${DATE}/${CYCLE}/ \
    --variables t2m,u10,v10,tp \
    --output gs://${BUCKET}/zarr/gfs_${DATE}_${CYCLE}.zarr

echo "=== Complete ==="
```

## Recommended Data Sources by Use Case

### For Development/Testing
- **AWS Public Datasets**: Free, no authentication required
- **Small date ranges**: Download a few days manually
- **Historical data**: Use archived datasets

### For Production
- **Set up your own GCS pipeline**: Sync from public sources
- **Use multiple sources**: Redundancy for reliability
- **Automate with Cloud Functions**: Trigger on schedule
- **Monitor data freshness**: Alert if data is delayed

### For Research
- **Copernicus CDS**: Comprehensive historical data
- **Google Earth Engine**: Large-scale analysis
- **ECMWF Open Data**: High-quality forecasts

## Data Availability and Latency

### GFS
- **Update frequency**: 4 times daily (00z, 06z, 12z, 18z)
- **Latency**: ~3-4 hours after cycle time
- **Retention**: Varies by source (typically 7-30 days)

### ECMWF
- **Update frequency**: 2 times daily (00z, 12z)
- **Latency**: ~6-8 hours after cycle time
- **Retention**: Varies by source

## Cost Considerations

### Storage Costs (GCS)
- Standard storage: $0.020 per GB/month
- Nearline (30-day): $0.010 per GB/month
- Coldline (90-day): $0.004 per GB/month

### Typical Data Volumes
- GFS 0.25° single cycle (120h): ~50-100 GB
- ECMWF HRES single cycle (240h): ~100-200 GB
- Monthly storage (daily cycles): ~3-6 TB

### Cost Optimization
1. Use lifecycle policies to move old data to Nearline/Coldline
2. Delete intermediate GRIB files after processing to Zarr
3. Use regional buckets to minimize egress
4. Compress Zarr archives aggressively

## Authentication and Permissions

### Required GCS Permissions

For source bucket (if you own it):
- `storage.objects.get`
- `storage.objects.list`

For destination bucket:
- `storage.objects.create`
- `storage.objects.delete` (if overwrite enabled)
- `storage.buckets.get`

### Service Account Setup

```bash
# Create service account
gcloud iam service-accounts create nwp-pipeline

# Grant permissions
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:nwp-pipeline@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"

# Create key
gcloud iam service-accounts keys create key.json \
    --iam-account=nwp-pipeline@PROJECT_ID.iam.gserviceaccount.com
```

## Verifying Data Sources

Before using a data source, verify it's accessible:

```python
from google.cloud import storage

def verify_gcs_path(bucket_name, prefix):
    """Verify GCS bucket and path are accessible."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    
    blobs = list(bucket.list_blobs(prefix=prefix, max_results=5))
    
    if blobs:
        print(f"✓ Found {len(blobs)} files in gs://{bucket_name}/{prefix}")
        for blob in blobs:
            print(f"  - {blob.name}")
        return True
    else:
        print(f"✗ No files found in gs://{bucket_name}/{prefix}")
        return False

# Test
verify_gcs_path("your-bucket-name", "gfs/20240101/00/")
```

## Next Steps

1. **Identify your data source**: Choose from public datasets or set up your own
2. **Update source paths**: Modify `sources.py` to match your data structure
3. **Test with small dataset**: Download a single cycle to verify
4. **Automate the pipeline**: Set up scheduled downloads
5. **Monitor and maintain**: Track data freshness and costs

## Resources

- NOAA NOMADS: https://nomads.ncep.noaa.gov/
- AWS Open Data: https://registry.opendata.aws/
- ECMWF Open Data: https://www.ecmwf.int/en/forecasts/datasets/open-data
- Copernicus CDS: https://cds.climate.copernicus.eu/
- Google Earth Engine: https://earthengine.google.com/

## Support

If you need help setting up data sources:
1. Check the documentation of your chosen data provider
2. Review the examples in this repository
3. Test with small datasets first
4. Open an issue if you encounter problems
