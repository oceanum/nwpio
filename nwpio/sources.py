"""Data source definitions for NWP products."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List


@dataclass
class GribFileSpec:
    """Specification for a single GRIB file."""

    source_path: str
    destination_path: str
    lead_time: int
    forecast_time: datetime


class DataSource:
    """Base class for NWP data sources."""

    def __init__(
        self,
        product: str,
        resolution: str,
        cycle: datetime,
        max_lead_time: int,
        source_bucket: str,
        destination_bucket: str,
        destination_prefix: str = "",
        local_download_dir: str = None,
    ):
        self.product = product
        self.resolution = resolution
        self.cycle = cycle  # This is now a datetime representing the forecast initialization time
        self.max_lead_time = max_lead_time
        self.source_bucket = source_bucket
        self.destination_bucket = destination_bucket
        self.destination_prefix = destination_prefix
        self.local_download_dir = local_download_dir

    def get_file_list(self) -> List[GribFileSpec]:
        """Generate list of GRIB files to download."""
        raise NotImplementedError


class GFSSource(DataSource):
    """GFS data source configuration."""

    # GFS file naming patterns and intervals
    LEAD_TIME_INTERVALS = {
        (0, 120): 1,  # 0-120h: hourly
        (120, 240): 3,  # 120-240h: 3-hourly
        (240, 384): 12,  # 240-384h: 12-hourly
    }

    def get_file_list(self) -> List[GribFileSpec]:
        """Generate list of GFS GRIB files to download."""
        files = []
        cycle_hour = self.cycle.hour

        for lead_time in self._generate_lead_times():
            # GFS path pattern: gfs.YYYYMMDD/HH/atmos/gfs.tHHz.pgrb2.RES.fFFF
            date_str = self.cycle.strftime("%Y%m%d")
            cycle_str = f"{cycle_hour:02d}"
            lead_str = f"{lead_time:03d}"

            source_path = (
                f"gs://{self.source_bucket}/gfs.{date_str}/{cycle_str}/atmos/"
                f"gfs.t{cycle_str}z.pgrb2.{self.resolution}.f{lead_str}"
            )

            # Generate destination path (local or GCS)
            if self.destination_bucket:
                dest_path = (
                    f"gs://{self.destination_bucket}/{self.destination_prefix}"
                    f"gfs/{self.resolution}/{date_str}/{cycle_str}/"
                    f"gfs.t{cycle_str}z.pgrb2.{self.resolution}.f{lead_str}"
                )
            else:
                # Local download path
                import os
                local_dir = self.local_download_dir or "/tmp/nwp-data"
                dest_path = os.path.join(
                    local_dir,
                    f"gfs/{self.resolution}/{date_str}/{cycle_str}",
                    f"gfs.t{cycle_str}z.pgrb2.{self.resolution}.f{lead_str}"
                )

            files.append(
                GribFileSpec(
                    source_path=source_path,
                    destination_path=dest_path,
                    lead_time=lead_time,
                    forecast_time=self.cycle + timedelta(hours=lead_time),
                )
            )

        return files

    def _generate_lead_times(self) -> List[int]:
        """Generate lead times based on GFS intervals."""
        lead_times = []
        for (start, end), interval in self.LEAD_TIME_INTERVALS.items():
            if start >= self.max_lead_time:
                break
            max_lt = min(end, self.max_lead_time)
            lead_times.extend(range(start, max_lt + 1, interval))
        return sorted(set(lead_times))


class ECMWFSource(DataSource):
    """ECMWF data source configuration."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_ensemble = self.product == "ecmwf-ens"

    def get_file_list(self) -> List[GribFileSpec]:
        """Generate list of ECMWF GRIB files to download."""
        files = []
        cycle_hour = self.cycle.hour

        for lead_time in self._generate_lead_times():
            date_str = self.cycle.strftime("%Y%m%d")
            cycle_str = f"{cycle_hour:02d}"
            lead_str = f"{lead_time:03d}"

            # ECMWF path pattern varies by source
            # This is a generic pattern - adjust based on actual GCS structure
            product_type = "ens" if self.is_ensemble else "hres"
            source_path = (
                f"gs://{self.source_bucket}/ecmwf/{product_type}/"
                f"{date_str}/{cycle_str}/{self.resolution}/"
                f"ecmwf.{product_type}.{cycle_str}z.{self.resolution}.f{lead_str}.grib"
            )

            dest_path = (
                f"gs://{self.destination_bucket}/{self.destination_prefix}"
                f"ecmwf/{product_type}/{self.resolution}/{date_str}/{cycle_str}/"
                f"ecmwf.{product_type}.{cycle_str}z.{self.resolution}.f{lead_str}.grib"
            )

            files.append(
                GribFileSpec(
                    source_path=source_path,
                    destination_path=dest_path,
                    lead_time=lead_time,
                    forecast_time=self.cycle + timedelta(hours=lead_time),
                )
            )

        return files

    def _generate_lead_times(self) -> List[int]:
        """Generate lead times for ECMWF."""
        # ECMWF typically has hourly output up to max lead time
        if self.is_ensemble:
            # Ensemble: 3-hourly for extended range
            if self.max_lead_time <= 144:
                return list(range(0, self.max_lead_time + 1, 3))
            else:
                # 3-hourly up to 144h, then 6-hourly
                lead_times = list(range(0, 145, 3))
                lead_times.extend(range(150, self.max_lead_time + 1, 6))
                return lead_times
        else:
            # HRES: hourly up to 90h, then 3-hourly
            if self.max_lead_time <= 90:
                return list(range(0, self.max_lead_time + 1, 1))
            else:
                lead_times = list(range(0, 91, 1))
                lead_times.extend(range(93, self.max_lead_time + 1, 3))
                return lead_times


def create_data_source(
    product: str,
    resolution: str,
    cycle: datetime,
    max_lead_time: int,
    source_bucket: str,
    destination_bucket: str,
    destination_prefix: str = "",
    local_download_dir: str = None,
) -> DataSource:
    """Factory function to create appropriate data source."""
    if product == "gfs":
        return GFSSource(
            product=product,
            resolution=resolution,
            cycle=cycle,
            max_lead_time=max_lead_time,
            source_bucket=source_bucket,
            destination_bucket=destination_bucket,
            destination_prefix=destination_prefix,
            local_download_dir=local_download_dir,
        )
    elif product in ["ecmwf-hres", "ecmwf-ens"]:
        return ECMWFSource(
            product=product,
            resolution=resolution,
            cycle=cycle,
            max_lead_time=max_lead_time,
            source_bucket=source_bucket,
            destination_bucket=destination_bucket,
            destination_prefix=destination_prefix,
            local_download_dir=local_download_dir,
        )
    else:
        raise ValueError(f"Unknown product: {product}")
