# API Overview

NWPIO provides both a command-line interface and a Python API.

## Python API

### Main Classes

- **[GribDownloader](downloader.md)** - Download GRIB files from cloud archives
- **[GribProcessor](processor.md)** - Process GRIB files to Zarr format
- **[DownloadConfig](config.md#downloadconfig)** - Download configuration
- **[ProcessConfig](config.md#processconfig)** - Processing configuration
- **[WorkflowConfig](config.md#workflowconfig)** - Combined workflow configuration

### Quick Example

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
)
processor = GribProcessor(config)
processor.process()
```

## CLI

### Commands

- **`nwpio download`** - Download GRIB files
- **`nwpio process`** - Process GRIB to Zarr
- **`nwpio run`** - Run complete workflow
- **`nwpio init-config`** - Generate sample configuration

See [CLI Reference](cli.md) for details.

## Next Steps

- [Configuration API](config.md)
- [Downloader API](downloader.md)
- [Processor API](processor.md)
- [CLI Reference](cli.md)
