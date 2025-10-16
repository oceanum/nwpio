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
    cycle: datetime = Field(description="Forecast initialization time (cycle)")
    max_lead_time: int = Field(description="Maximum lead time in hours", gt=0)
    source_bucket: str = Field(description="Source GCS bucket containing GRIB files")
    destination_bucket: str = Field(
        description="Destination GCS bucket for downloaded files"
    )
    destination_prefix: Optional[str] = Field(
        default=None, description="Optional prefix for destination paths"
    )
    overwrite: bool = Field(default=False, description="Overwrite existing files")

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

    grib_path: str = Field(description="Path to GRIB files (local or GCS)")
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


class WorkflowConfig(BaseModel):
    """Combined configuration for download and process workflow."""

    download: DownloadConfig = Field(description="Download configuration")
    process: ProcessConfig = Field(description="Process configuration")
    cleanup_grib: bool = Field(
        default=False, description="Delete GRIB files after processing"
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
