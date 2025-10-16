# Installation

## Requirements

- **Python**: 3.9 or higher
- **eccodes**: Required for GRIB file support
- **Google Cloud**: Access to GCS buckets

## Install from PyPI

```bash
pip install nwpio
```

## Install from Source

For development or to get the latest features:

```bash
git clone https://github.com/yourusername/nwpio.git
cd nwpio
pip install -e .
```

### With Development Dependencies

```bash
pip install -e ".[dev]"
```

This includes:
- pytest - Testing framework
- black - Code formatter
- ruff - Linter
- mypy - Type checker

## System Dependencies

### eccodes

NWPIO uses cfgrib which requires the eccodes library.

=== "Ubuntu/Debian"

    ```bash
    sudo apt-get update
    sudo apt-get install libeccodes-dev
    ```

=== "macOS"

    ```bash
    brew install eccodes
    ```

=== "Conda"

    ```bash
    conda install -c conda-forge eccodes
    ```

## Google Cloud Authentication

NWPIO requires authentication to access Google Cloud Storage.

### Option 1: Application Default Credentials

```bash
gcloud auth application-default login
```

### Option 2: Service Account

1. Create a service account in Google Cloud Console
2. Download the JSON key file
3. Set the environment variable:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

### Option 3: Workload Identity (GKE)

If running on Google Kubernetes Engine, configure Workload Identity for your pods.

## Verify Installation

Test that everything is installed correctly:

```bash
# Check CLI is available
nwpio --version

# Test Python import
python -c "from nwpio import GribDownloader, GribProcessor; print('✓ NWPIO installed successfully')"
```

## Docker Installation

A Dockerfile is provided for containerized deployments:

```bash
docker build -t nwpio .
docker run nwpio nwpio --help
```

## Troubleshooting

### ImportError: No module named 'eccodes'

The eccodes library is not installed. Follow the [system dependencies](#eccodes) instructions above.

### Authentication Errors

Ensure your Google Cloud credentials are properly configured:

```bash
gcloud auth application-default login
```

Or set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable.

### Permission Denied on GCS

Verify your service account or user has the following permissions:
- `storage.objects.get` - Read from source bucket
- `storage.objects.create` - Write to destination bucket
- `storage.objects.list` - List bucket contents

## Next Steps

- [Quick Start](quickstart.md) - Get started with NWPIO
- [Configuration](configuration.md) - Learn about configuration options
