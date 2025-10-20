# Architecture

## Overview

The NWP Download library is designed with a modular architecture to handle downloading and processing of numerical weather prediction data from cloud archives.

## Project Structure

```
nwpio/
├── nwpio/                     # Main library package
│   ├── __init__.py           # Package exports
│   ├── config.py             # Pydantic configuration models
│   ├── sources.py            # Data source definitions (GFS/ECMWF)
│   ├── downloader.py         # Parallel GRIB file downloader
│   ├── processor.py          # GRIB to Zarr converter
│   ├── utils.py              # GCS utilities and helpers
│   └── cli.py                # Click-based CLI interface
│
├── examples/                  # Usage examples
│   ├── config-ecmwf-wind10m.yaml
│   ├── config-production.yaml
│   └── example_usage.py
│
├── docs/                      # Documentation
│   ├── API.md                # Complete API reference
│   ├── ARCHITECTURE.md       # System design and architecture
│   ├── DEPLOYMENT.md         # Deployment and operations guide
│   ├── getting-started/      # Getting started guides
│   ├── guide/                # User guides
│   └── api/                  # API documentation
│
├── tests/                     # Test suite
│   ├── __init__.py
│   └── test_config.py
│
├── pyproject.toml            # Modern Python packaging
├── requirements.txt          # Production dependencies
├── Dockerfile                # Container image definition
├── README.md                 # Main documentation
└── LICENSE                   # MIT License
```

## Components

### 1. Configuration (`config.py`)

Uses Pydantic models for type-safe configuration:

- **DownloadConfig**: Specifies what data to download (product, resolution, time, cycle, lead time)
- **ProcessConfig**: Defines how to process GRIB files (variables, output format, chunking)
- **WorkflowConfig**: Combines download and process configurations for end-to-end workflows

Benefits:
- Type validation at runtime
- Clear documentation through field descriptions
- Easy serialization to/from YAML

### 2. Data Sources (`sources.py`)

Defines product-specific logic for generating file lists:

- **DataSource**: Base class defining the interface
- **GFSSource**: Implements GFS-specific file naming and lead time intervals
- **ECMWFSource**: Implements ECMWF-specific patterns for HRES and ENS products

Key features:
- Product-aware lead time generation (e.g., GFS hourly up to 120h, then 3-hourly)
- Flexible path templates for different archive structures
- Factory pattern for creating appropriate source instances

### 3. Downloader (`downloader.py`)

Handles efficient parallel downloading from GCS:

- **GribDownloader**: Main class for downloading GRIB files
  - Parallel downloads using ThreadPoolExecutor
  - Progress tracking with tqdm
  - Skip existing files (unless overwrite enabled)
  - Verification of downloaded files

Features:
- GCS-to-GCS copying (no local storage required)
- Configurable parallelism
- Dry-run mode for previewing downloads
- Robust error handling and logging

### 4. Processor (`processor.py`)

Converts GRIB files to Zarr format:

- **GribProcessor**: Main class for GRIB processing
  - Uses xarray and cfgrib for GRIB reading
  - Combines multiple GRIB files along time dimension
  - Extracts specified variables
  - Writes to Zarr with compression

Features:
- Automatic file discovery (local or GCS)
- Flexible variable selection
- Configurable chunking for optimal performance
- Multiple compression algorithms
- GRIB key filtering for specific levels/types

### 5. Utilities (`utils.py`)

Common utility functions:

- GCS path parsing and validation
- Blob existence checking
- File copying and uploading
- Human-readable formatting

### 6. CLI (`cli.py`)

Command-line interface using Click:

- **download**: Download GRIB files
- **process**: Process GRIB to Zarr
- **run**: Execute complete workflow from config file
- **init-config**: Generate sample configuration

## Data Flow

```
┌─────────────────┐
│  Configuration  │
│   (YAML/Code)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Data Source    │
│  (GFS/ECMWF)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Downloader    │
│  (GCS → GCS)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   GRIB Files    │
│   (in GCS)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Processor     │
│ (GRIB → Zarr)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Zarr Archive   │
│   (in GCS)      │
└─────────────────┘
```

## Design Decisions

### 1. Cloud-Native

- Designed for GCS-to-GCS operations
- No local storage required for large GRIB files
- Uses gcsfs and fsspec for transparent cloud access

### 2. Parallel Processing

- ThreadPoolExecutor for I/O-bound download operations
- Configurable worker count for different network conditions
- Progress tracking for long-running operations

### 3. Modular Design

- Each component has a single responsibility
- Easy to extend with new products or data sources
- Configuration-driven behavior

### 4. Type Safety

- Pydantic models for configuration validation
- Type hints throughout the codebase
- Catch errors early at configuration time

### 5. Production Ready

- Comprehensive logging
- Error handling and recovery
- Dry-run modes for testing
- Docker and Kubernetes support

## Extension Points

### Adding a New Product

1. Create a new class inheriting from `DataSource`
2. Implement `get_file_list()` method
3. Add product to `create_data_source()` factory
4. Update configuration validation

### Custom Processing

The processor can be extended to:
- Apply custom transformations to data
- Compute derived variables
- Implement different output formats
- Add quality control checks

### Alternative Storage

While designed for GCS, the architecture can be adapted for:
- AWS S3 (using s3fs)
- Azure Blob Storage (using adlfs)
- Local filesystem
- HTTP/HTTPS endpoints

## Performance Considerations

### Download Performance

- Parallel downloads: 10 workers by default
- GCS-to-GCS copying is fast (no egress)
- Skip existing files to avoid redundant transfers

### Processing Performance

- Chunking strategy affects read/write performance
- Default: chunk by time (1 timestep per chunk)
- Larger spatial chunks for better compression
- Compression reduces storage but adds CPU overhead

### Memory Usage

- GRIB files are processed one at a time
- Xarray uses lazy loading with Dask
- Memory usage scales with chunk size
- Monitor memory for large datasets

## Security

### Authentication

- Uses Google Cloud SDK authentication
- Service accounts for production deployments

### Credentials

- Never hardcode credentials
- Use environment variables or mounted secrets
- Follow principle of least privilege

## Monitoring

### Logging

- Structured logging with timestamps
- Different levels (DEBUG, INFO, WARNING, ERROR)
- Separate logs for download and processing

### Metrics

Consider adding:
- Download success/failure rates
- Processing duration
- Data volume transferred
- Storage costs

## Future Enhancements

1. **Incremental Updates**: Only download new forecast cycles
2. **Data Validation**: Verify GRIB file integrity
3. **Metadata Management**: Track provenance and lineage
4. **Caching**: Cache frequently accessed data
5. **Notifications**: Alert on failures or completion
6. **Web Interface**: Dashboard for monitoring and configuration
