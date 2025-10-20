# ECMWF Variables Guide

## Overview

ECMWF open data (available on AWS S3) provides a **subset** of variables compared to the full ECMWF dataset. Not all variables you might expect are available in the free public archive.

!!! warning "Limited Variable Set"
    The ECMWF open data archive contains only commonly-used variables. Many specialized variables from the full ECMWF dataset are not available.

## Available Variables

### Surface/2m Level

Filter: `typeOfLevel: heightAboveGround, level: 2`

| Variable | Description |
|----------|-------------|
| `t2m` | 2 metre temperature |
| `d2m` | 2 metre dewpoint temperature |

**Example:**
```yaml
process:
  - filter_by_keys:
      typeOfLevel: heightAboveGround
      level: 2
    variables: [t2m, d2m]
    zarr_path: gs://bucket/surface_temp_{cycle:%Y%m%d}.zarr
```

### 10m Level

Filter: `typeOfLevel: heightAboveGround, level: 10`

| Variable | Description |
|----------|-------------|
| `u10` | 10 metre U wind component |
| `v10` | 10 metre V wind component |

**Example:**
```yaml
process:
  - filter_by_keys:
      typeOfLevel: heightAboveGround
      level: 10
    variables: [u10, v10]
    zarr_path: gs://bucket/wind10m_{cycle:%Y%m%d}.zarr
```

### Mean Sea Level

Filter: `typeOfLevel: meanSea`

| Variable | Description |
|----------|-------------|
| `msl` | Mean sea level pressure |
| `prmsl` | Pressure reduced to MSL (alternative name) |

**Example:**
```yaml
process:
  - filter_by_keys:
      typeOfLevel: meanSea
    variables: [msl]
    zarr_path: gs://bucket/msl_{cycle:%Y%m%d}.zarr
```

### Surface Variables

Filter: `typeOfLevel: surface`

| Variable | Description |
|----------|-------------|
| `tp` | Total precipitation |
| `tprate` | Total precipitation rate |
| `skt` | Skin temperature |
| `tcwv` | Total column water vapour |
| `lsm` | Land-sea mask |

**Example:**
```yaml
process:
  - filter_by_keys:
      typeOfLevel: surface
    variables: [tp, skt]
    zarr_path: gs://bucket/surface_{cycle:%Y%m%d}.zarr
```

### Pressure Levels

Filter: `typeOfLevel: isobaricInhPa`

Common levels: 1000, 925, 850, 700, 500, 300, 250, 200, 100 hPa

| Variable | Description |
|----------|-------------|
| `t` | Temperature |
| `u` | U component of wind |
| `v` | V component of wind |
| `z` | Geopotential |
| `q` | Specific humidity |
| `r` | Relative humidity |

**Example:**
```yaml
process:
  - filter_by_keys:
      typeOfLevel: isobaricInhPa
      level: 500  # 500 hPa level
    variables: [t, u, v, z]
    zarr_path: gs://bucket/pressure_500_{cycle:%Y%m%d}.zarr
```

## Inspecting Available Variables

### Method 1: Using grib_ls (eccodes)

If you have eccodes installed:

```bash
grib_ls -p shortName,typeOfLevel,level /path/to/ecmwf.hres.00z.0p25.f000.grib
```

### Method 2: Using Python with cfgrib

```python
import xarray as xr

# Open without filters to see everything
ds = xr.open_dataset(
    "/path/to/ecmwf.hres.00z.0p25.f000.grib",
    engine="cfgrib"
)
print("Variables:", list(ds.data_vars.keys()))
print("Coordinates:", list(ds.coords.keys()))
```

### Method 3: Try Different Filter Combinations

```python
import xarray as xr

file = "/path/to/ecmwf.hres.00z.0p25.f000.grib"

# Try surface level
try:
    ds = xr.open_dataset(
        file, 
        engine="cfgrib", 
        backend_kwargs={"filter_by_keys": {"typeOfLevel": "surface"}}
    )
    print("Surface vars:", list(ds.data_vars.keys()))
except Exception as e:
    print(f"Surface error: {e}")

# Try heightAboveGround
try:
    ds = xr.open_dataset(
        file,
        engine="cfgrib",
        backend_kwargs={"filter_by_keys": {"typeOfLevel": "heightAboveGround"}}
    )
    print("heightAboveGround vars:", list(ds.data_vars.keys()))
except Exception as e:
    print(f"heightAboveGround error: {e}")

# Try pressure levels
try:
    ds = xr.open_dataset(
        file,
        engine="cfgrib",
        backend_kwargs={"filter_by_keys": {"typeOfLevel": "isobaricInhPa"}}
    )
    print("Pressure level vars:", list(ds.data_vars.keys()))
    print("Available levels:", ds.isobaricInhPa.values)
except Exception as e:
    print(f"Pressure level error: {e}")
```

## Common Issues

### Variable Not Found

If a variable isn't found, it might:

1. **Not be in the open data subset** - Check the [ECMWF Open Data Documentation](https://confluence.ecmwf.int/display/DAC/ECMWF+open+data)
2. **Be named differently** - Use `grib_ls` to see actual variable names
3. **Require different filter keys** - Try different `typeOfLevel` values
4. **Only be available at certain forecast hours** - Some variables are only in specific lead times

### Multiple Messages Error

Some GRIB files contain multiple "messages" for the same variable at different levels. Use `filter_by_keys` to disambiguate:

```yaml
filter_by_keys:
  typeOfLevel: surface
  stepType: instant  # vs 'accum' for accumulated variables
```

### Variable Name Variations

Some variables have multiple names:
- Mean sea level pressure: `msl` or `prmsl`
- Temperature: `t` (pressure levels) or `t2m` (2m level)

## ECMWF Cycle Coverage

ECMWF HRES runs 4 times daily with different forecast horizons:

| Cycle | Lead Time | Variables |
|-------|-----------|-----------|
| 00z | 240 hours (10 days) | Full set |
| 06z | 90 hours (3.75 days) | Full set |
| 12z | 240 hours (10 days) | Full set |
| 18z | 90 hours (3.75 days) | Full set |

## Official Documentation

For the complete and up-to-date list of available variables:

- [ECMWF Open Data Documentation](https://confluence.ecmwf.int/display/DAC/ECMWF+open+data)
- [ECMWF Parameter Database](https://codes.ecmwf.int/grib/param-db/)
- [ECMWF Open Data on AWS](https://registry.opendata.aws/ecmwf-forecasts/)

## Example: Multi-Variable Processing

Download once, process multiple variable sets:

```yaml
download:
  product: ecmwf-hres
  resolution: 0p25
  cycle: "2024-01-01T00:00:00"
  max_lead_time: 240
  source_bucket: ecmwf-forecasts
  local_download_dir: /tmp/nwp-data

process:
  # 10m winds
  - filter_by_keys:
      typeOfLevel: heightAboveGround
      level: 10
    variables: [u10, v10]
    zarr_path: gs://bucket/wind10m_{cycle:%Y%m%d}_{cycle:%Hz}.zarr
    
  # 2m temperature
  - filter_by_keys:
      typeOfLevel: heightAboveGround
      level: 2
    variables: [t2m, d2m]
    zarr_path: gs://bucket/temp2m_{cycle:%Y%m%d}_{cycle:%Hz}.zarr
    
  # Mean sea level pressure
  - filter_by_keys:
      typeOfLevel: meanSea
    variables: [msl]
    zarr_path: gs://bucket/msl_{cycle:%Y%m%d}_{cycle:%Hz}.zarr
    
  # Surface precipitation
  - filter_by_keys:
      typeOfLevel: surface
    variables: [tp]
    zarr_path: gs://bucket/precip_{cycle:%Y%m%d}_{cycle:%Hz}.zarr
```

Run with:
```bash
nwpio run --config config.yaml --max-workers 8
```
