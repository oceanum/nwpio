# NWPIO

**Download and process NWP forecast data from cloud archives**

NWPIO is a Python library for downloading GRIB files from cloud archives and converting them to Zarr format for efficient analysis. It supports various NWP models such as GFS and ECMWF with a simple, intuitive API.

## Features

✨ **Cloud-Native** - Direct GCS-to-GCS operations, no local storage required  
⚡ **Fast** - Parallel downloads with configurable workers  
🎯 **Flexible** - Support for multiple products, resolutions, and cycles  
📦 **Zarr Output** - Efficient chunked storage for large datasets  
🛠️ **CLI & Python API** - Use from command line or integrate into your code  
🔧 **Type-Safe** - Pydantic models with runtime validation  

## Quick Example

### CLI

```bash
# Download GFS data
nwpio download \
    --product gfs \
    --resolution 0p25 \
    --cycle 2024-01-01T00:00:00 \
    --max-lead-time 120 \
    --source-bucket global-forecast-system \
    --dest-bucket your-bucket

# Process to Zarr
nwpio process \
    --grib-path gs://your-bucket/nwp-data/ \
    --variables u10,v10,t2m \
    --output gs://your-bucket/forecast_{cycle:%Y%m%d}_{cycle:%Hz}.zarr \
    --write-local-first
```

### Python API

```python
from datetime import datetime
from nwpio import GribDownloader, GribProcessor
from nwpio.config import DownloadConfig, ProcessConfig

# Download
config = DownloadConfig(
    product="gfs",
    resolution="0p25",
    cycle=datetime(2024, 1, 1, 0),
    max_lead_time=120,
    source_bucket="global-forecast-system",
    destination_bucket="your-bucket",
)
downloader = GribDownloader(config)
files = downloader.download()

# Process
config = ProcessConfig(
    grib_path="gs://your-bucket/nwp-data/",
    variables=["u10", "v10", "t2m"],
    output_path="gs://your-bucket/forecast_{cycle:%Y%m%d}_{cycle:%Hz}.zarr",
    write_local_first=True,
)
processor = GribProcessor(config)
processor.process()
```

## Supported Products

| Product | Resolution | Cycles | Max Lead Time |
|---------|-----------|--------|---------------|
| **GFS** | 0.25°, 0.5°, 1.0° | 00z, 06z, 12z, 18z | 384 hours |
| **ECMWF HRES** | 0.1°, 0.25° | 00z, 12z | 240 hours |
| **ECMWF ENS** | 0.25°, 0.5° | 00z, 12z | 360 hours |

## Installation

```bash
pip install nwpio
```

For development:

```bash
git clone https://github.com/yourusername/nwpio.git
cd nwpio
pip install -e ".[dev]"
```

## Next Steps

- [Quick Start Guide](getting-started/quickstart.md) - Get up and running in 5 minutes
- [Configuration](getting-started/configuration.md) - Learn about YAML configuration
- [User Guide](guide/downloading.md) - Detailed usage instructions
- [API Reference](api/overview.md) - Complete API documentation

## Requirements

- Python 3.9+
- Google Cloud Storage access
- eccodes library (for GRIB support)

## License

MIT License - see [LICENSE](about/license.md) for details.
