# NWP Download - Project Overview

## Summary

A production-ready Python library for downloading and processing Numerical Weather Prediction (NWP) forecast data from GFS and ECMWF. Designed for cloud-native workflows with GCS integration and parallel processing.

## Project Structure

```
nwp-download/
├── nwp_download/              # Main library package
│   ├── __init__.py           # Package exports
│   ├── config.py             # Pydantic configuration models
│   ├── sources.py            # Data source definitions (GFS/ECMWF)
│   ├── downloader.py         # Parallel GRIB file downloader
│   ├── processor.py          # GRIB to Zarr converter
│   ├── utils.py              # GCS utilities and helpers
│   └── cli.py                # Click-based CLI interface
│
├── examples/                  # Usage examples
│   ├── example_config.yaml   # Sample configuration file
│   └── example_usage.py      # Python API examples
│
├── docs/                      # Documentation
│   ├── API.md                # Complete API reference
│   ├── ARCHITECTURE.md       # System design and architecture
│   └── DEPLOYMENT.md         # Deployment and operations guide
│
├── tests/                     # Test suite
│   ├── __init__.py
│   └── test_config.py        # Configuration tests
│
├── pyproject.toml            # Modern Python packaging
├── requirements.txt          # Production dependencies
├── Dockerfile                # Container image definition
├── README.md                 # Main documentation
├── QUICKSTART.md             # 5-minute getting started guide
├── LICENSE                   # MIT License
└── .gitignore               # Git ignore patterns
```

## Key Features

### 1. **Flexible Data Download**
- Support for GFS and ECMWF (HRES/ENS) products
- Multiple resolutions (0.25°, 0.5°, 1.0°, etc.)
- Configurable forecast cycles (00z, 06z, 12z, 18z)
- Variable lead time horizons (up to 384h for GFS)
- Parallel downloads with configurable workers
- GCS-to-GCS copying (no local storage needed)

### 2. **GRIB Processing**
- Extract specific variables from GRIB files
- Combine multiple files along time dimension
- Convert to Zarr format for efficient access
- Configurable chunking strategies
- Multiple compression algorithms (zstd, lz4)
- Filter by GRIB keys (level, type, etc.)

### 3. **Production Ready**
- Type-safe configuration with Pydantic
- Comprehensive error handling and logging
- Progress tracking for long operations
- Dry-run mode for testing
- Docker support

### 4. **Cloud Native**
- Designed for Google Cloud Storage
- No local disk requirements
- Scalable parallel processing
- Service account authentication
- Regional deployment support

## Core Components

### Configuration System
- **DownloadConfig**: Product, resolution, time, cycle, lead time
- **ProcessConfig**: Variables, output path, chunking, compression
- **WorkflowConfig**: Combined download + process + cleanup

### Data Sources
- **GFSSource**: GFS-specific file patterns and intervals
- **ECMWFSource**: ECMWF HRES/ENS patterns
- **Factory pattern**: Automatic source selection

### Downloader
- Parallel ThreadPoolExecutor for I/O operations
- Smart file skipping (avoid re-downloads)
- Verification and manifest generation
- Progress bars with tqdm

### Processor
- xarray + cfgrib for GRIB reading
- Automatic time dimension concatenation
- Variable filtering and selection
- Zarr output with compression
- GCS and local filesystem support

### CLI
- `download`: Download GRIB files
- `process`: Convert GRIB to Zarr
- `run`: Execute complete workflow
- `init-config`: Generate sample config

## Usage Patterns

### 1. Command Line
```bash
# Generate config
nwp-download init-config --output config.yaml

# Run workflow
nwp-download run --config config.yaml

# Download only
nwp-download download --product gfs --resolution 0p25 ...

# Process only
nwp-download process --grib-path gs://... --variables t2m,u10,v10
```

### 2. Python API
```python
from nwp_download import GribDownloader, GribProcessor
from nwp_download import DownloadConfig, ProcessConfig

# Download
config = DownloadConfig(...)
downloader = GribDownloader(config)
files = downloader.download()

# Process
config = ProcessConfig(...)
processor = GribProcessor(config)
processor.process()
```

## Deployment Options

### Local Development
```bash
pip install -e .
nwp-download --help
```

### Docker
```bash
docker build -t nwp-download .
docker run nwp-download run --config /config/config.yaml
```

## Configuration Example

```yaml
download:
  product: gfs
  resolution: 0p25
  forecast_time: "2024-01-01T00:00:00"
  cycle: 00z
  max_lead_time: 120
  source_bucket: gcp-public-data-arco-era5
  destination_bucket: your-bucket-name
  destination_prefix: nwp-data/

process:
  grib_path: gs://your-bucket-name/nwp-data/
  variables: [t2m, u10, v10, tp]
  output_path: gs://your-bucket-name/output.zarr
  compression: default

cleanup_grib: false
```

## Dependencies

### Core
- **google-cloud-storage**: GCS operations
- **xarray**: Multi-dimensional arrays
- **cfgrib**: GRIB file reading
- **zarr**: Chunked array storage
- **pydantic**: Configuration validation
- **click**: CLI framework

### Optional
- **pytest**: Testing
- **black**: Code formatting
- **ruff**: Linting

## Supported Products

### GFS (Global Forecast System)
- Resolutions: 0.25°, 0.5°, 1.0°
- Cycles: 00z, 06z, 12z, 18z
- Lead times: Up to 384 hours
- Intervals: Hourly (0-120h), 3-hourly (120-240h), 12-hourly (240-384h)

### ECMWF
- Products: HRES (High Resolution), ENS (Ensemble)
- Resolutions: 0.1°, 0.25°
- Cycles: 00z, 12z
- Lead times: Up to 240h (HRES), 360h (ENS)
- Intervals: Hourly/3-hourly depending on product

## Common Variables

- **t2m**: 2-meter temperature
- **u10, v10**: 10-meter wind components
- **tp**: Total precipitation
- **msl**: Mean sea level pressure
- **sp**: Surface pressure
- **tcc**: Total cloud cover
- **t, u, v, z, r**: Pressure level variables

## Performance Characteristics

### Download
- 10 parallel workers by default
- ~100-200 files per forecast cycle
- GCS-to-GCS: Fast (no egress)
- Typical time: 5-15 minutes for 120h forecast

### Processing
- Memory: ~4-8 GB recommended
- CPU: Benefits from multiple cores (compression)
- Typical time: 10-30 minutes depending on variables
- Output size: ~1-5 GB per forecast (compressed)

## Security Best Practices

1. Use service accounts with minimal permissions
2. Never commit credentials to version control
3. Use Workload Identity in Kubernetes
4. Enable audit logging
5. Implement network policies
6. Rotate credentials regularly

## Monitoring and Observability

### Logging
- Structured logs with timestamps
- Multiple log levels (DEBUG, INFO, WARNING, ERROR)
- Progress tracking for long operations

### Metrics (to implement)
- Download success/failure rates
- Processing duration
- Data volume transferred
- Storage costs

### Alerting (to implement)
- Job failures
- Excessive runtime
- Storage quota exceeded

## Next Steps for Production

1. **Testing**: Add comprehensive unit and integration tests
2. **CI/CD**: Set up automated testing and deployment
3. **Monitoring**: Implement metrics collection and alerting
4. **Documentation**: Add more examples and tutorials
5. **Optimization**: Profile and optimize performance bottlenecks
6. **Features**: Add incremental updates, data validation, caching

## Getting Started

1. Read [QUICKSTART.md](QUICKSTART.md) for 5-minute setup
2. Review [examples/](examples/) for usage patterns
3. Check [docs/API.md](docs/API.md) for complete API reference
4. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for production deployment

## Contributing

Contributions welcome! Areas for improvement:
- Additional NWP products (ICON, ARPEGE, etc.)
- Alternative storage backends (S3, Azure)
- Enhanced processing capabilities
- Performance optimizations
- Documentation improvements

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

- Documentation: See `docs/` directory
- Examples: See `examples/` directory
- Issues: Open a GitHub issue
- Questions: Check documentation first

---

**Built with ❤️ for the weather forecasting community**
