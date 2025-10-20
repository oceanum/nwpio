"""Configuration models for NWP download and processing."""

from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class DownloadConfig(BaseModel):
    """Configuration for downloading GRIB files."""

    product: Literal["gfs", "ecmwf-hres", "ecmwf-ens"] = Field(
        description="NWP product to download"
    )
    resolution: str = Field(
        description="Model resolution (e.g., '0p25' for 0.25 degrees)"
    )
    cycle: Optional[datetime] = Field(
        default=None,
        description="Forecast initialization time (cycle). Can be set via CLI --cycle or $CYCLE environment variable.",
    )
    max_lead_time: int = Field(description="Maximum lead time in hours", gt=0)
    source_bucket: str = Field(description="Source GCS bucket containing GRIB files")
    destination_bucket: Optional[str] = Field(
        default=None,
        description="Destination GCS bucket for downloaded files (if None, downloads to local)",
    )
    destination_prefix: Optional[str] = Field(
        default=None, description="Optional prefix for destination paths"
    )
    local_download_dir: Optional[str] = Field(
        default=None,
        description="Local directory to download files to (if destination_bucket is None)",
    )
    overwrite: bool = Field(default=False, description="Overwrite existing files")
    validate_before_download: bool = Field(
        default=True,
        description="Validate all files are available before starting download. "
        "Raises exception if files are missing (fail fast for retry logic).",
    )

    @field_validator("cycle")
    @classmethod
    def validate_cycle(cls, v: datetime, info) -> datetime:
        """Validate cycle hour matches product constraints."""
        product = info.data.get("product")
        cycle_hour = v.hour

        # Validate cycle hour is valid (0, 6, 12, 18)
        if cycle_hour not in [0, 6, 12, 18]:
            raise ValueError(f"Cycle hour must be 0, 6, 12, or 18, got {cycle_hour}")

        # ECMWF only supports 00z and 12z
        if product in ["ecmwf-hres", "ecmwf-ens"]:
            if cycle_hour not in [0, 12]:
                raise ValueError(
                    f"ECMWF only supports 00z and 12z cycles, got {cycle_hour:02d}z"
                )

        return v

    @field_validator("max_lead_time")
    @classmethod
    def validate_lead_time(cls, v: int, info) -> int:
        """Validate lead time is within product limits."""
        product = info.data.get("product")
        if product == "gfs" and v > 384:
            raise ValueError(f"GFS max lead time is 384 hours, got {v}")
        elif product == "ecmwf-hres" and v > 240:
            raise ValueError(f"ECMWF HRES max lead time is 240 hours, got {v}")
        elif product == "ecmwf-ens" and v > 360:
            raise ValueError(f"ECMWF ENS max lead time is 360 hours, got {v}")
        return v


class ProcessConfig(BaseModel):
    """Configuration for processing GRIB files to Zarr."""

    grib_path: Optional[str] = Field(
        default=None,
        description="Path to GRIB files (local or GCS). If None, will use downloaded files location.",
    )
    variables: List[str] = Field(
        description="List of variables to extract from GRIB files"
    )
    output_path: str = Field(
        description="Output path for Zarr archive (local or GCS). Supports {timestamp}, {date}, {time}, {cycle} placeholders"
    )
    filter_by_keys: Optional[dict] = Field(
        default=None,
        description="Additional GRIB key filters (e.g., {'typeOfLevel': 'surface'})",
    )
    chunks: Optional[dict] = Field(
        default=None,
        description="Chunking specification for Zarr (e.g., {'time': 1, 'latitude': 100})",
    )
    overwrite: bool = Field(
        default=False, description="Overwrite existing Zarr archive"
    )
    timestamp_format: str = Field(
        default="%Y%m%d_%H%M%S",
        description="Format string for {timestamp} placeholder (strftime format)",
    )
    write_local_first: bool = Field(
        default=False,
        description="Write to local temp directory first, then upload to GCS (helps with network issues)",
    )
    local_temp_dir: Optional[str] = Field(
        default=None,
        description="Local temporary directory for write_local_first (default: system temp dir)",
    )
    max_upload_workers: int = Field(
        default=16,
        description="Maximum number of parallel workers for uploading to GCS",
    )
    upload_timeout: int = Field(
        default=600,
        description="Timeout in seconds for individual file uploads to GCS (default: 600s)",
    )
    upload_max_retries: int = Field(
        default=3,
        description="Maximum number of retries for failed uploads (default: 3)",
    )
    verify_upload: bool = Field(
        default=True,
        description="Verify all files were uploaded successfully after upload completes",
    )
    max_grib_workers: int = Field(
        default=4,
        description="Maximum number of parallel workers for loading GRIB files (default: 4)",
    )
    clean_coords: bool = Field(
        default=True,
        description="Clean dataset coordinates before writing (keeps only time, latitude, longitude)",
    )
    rename_vars: Optional[dict] = Field(
        default=None,
        description="Rename variables before writing (e.g., {'u10': 'u', 'v10': 'v'})",
    )


class WorkflowConfig(BaseModel):
    """Combined configuration for download and process workflow."""

    download: DownloadConfig = Field(description="Download configuration")
    process: List[ProcessConfig] | None = Field(
        default=None,
        description="List of process configurations to run on downloaded GRIB files. Optional - can download without processing.",
    )
    cleanup_grib: bool = Field(
        default=False, description="Delete GRIB files after all processing is complete"
    )

    @classmethod
    def from_yaml(cls, path: Path) -> "WorkflowConfig":
        """Load configuration from YAML file."""
        import yaml

        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def to_yaml(self, path: Path) -> None:
        """Save configuration to YAML file."""
        import yaml

        with open(path, "w") as f:
            yaml.dump(self.model_dump(mode="json"), f, default_flow_style=False)
