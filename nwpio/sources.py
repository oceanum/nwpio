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

    def _generate_lead_times(self) -> List[int]:
        """Generate lead times based on product intervals."""
        raise NotImplementedError

    def get_next_lead_time(self) -> int:
        """
        Get the next lead time after max_lead_time.
        Used to verify the last required file is fully uploaded.

        Returns:
            Next lead time in hours, or None if max_lead_time is the last available
        """
        all_lead_times = self._generate_lead_times()

        # Find the next lead time after max_lead_time
        for lt in all_lead_times:
            if lt > self.max_lead_time:
                return lt

        # If max_lead_time is already at the end, calculate what the next would be
        # based on the interval pattern
        return None


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
                    f"gfs.t{cycle_str}z.pgrb2.{self.resolution}.f{lead_str}",
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

    def get_next_lead_time(self) -> int:
        """Get the next lead time after max_lead_time for validation."""
        # Find which interval range max_lead_time falls into
        for (start, end), interval in self.LEAD_TIME_INTERVALS.items():
            if start <= self.max_lead_time < end:
                # Calculate next lead time in this interval
                next_lt = self.max_lead_time + interval
                # Make sure it aligns with the interval grid
                offset = (self.max_lead_time - start) % interval
                if offset != 0:
                    next_lt = self.max_lead_time + (interval - offset)
                return min(next_lt, end)
            elif self.max_lead_time == end:
                # We're at the boundary, move to next interval
                next_intervals = [
                    (s, e, i)
                    for (s, e), i in self.LEAD_TIME_INTERVALS.items()
                    if s == end
                ]
                if next_intervals:
                    return next_intervals[0][0]  # Start of next interval
                return None
        return None


class ECMWFSource(DataSource):
    """ECMWF data source configuration."""

    def __init__(self, *args, source_type=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_ensemble = self.product == "ecmwf-ens"

        # Determine source type
        if source_type:
            self.source_type = source_type
        elif self.source_bucket == "ecmwf-forecasts":
            self.source_type = "aws"
        elif self.source_bucket == "ecmwf-open-data":
            self.source_type = "gcs"
        else:
            # Default to GCS for backward compatibility
            self.source_type = "gcs"

    def get_file_list(self) -> List[GribFileSpec]:
        """Discover and list ECMWF GRIB files available up to max_lead_time."""
        date_str = self.cycle.strftime("%Y%m%d")
        cycle_hour = self.cycle.hour
        cycle_str = f"{cycle_hour:02d}"
        product_type = "ens" if self.is_ensemble else "hres"

        # Route to appropriate source based on source_type
        if self.source_type == "aws":
            # Discover files from AWS S3
            return self._discover_s3_files(date_str, cycle_str, product_type)
        else:
            # Use GCS pattern (official ecmwf-open-data bucket)
            return self._discover_gcs_official_files(date_str, cycle_str, product_type)

    def _discover_s3_files(
        self, date_str: str, cycle_str: str, product_type: str
    ) -> List[GribFileSpec]:
        """Discover available files from AWS S3 up to max_lead_time."""
        import fsspec
        import re

        if self.is_ensemble:
            product_name = "enfo"
            product_suffix = "ef"
        else:
            product_name = "oper"
            product_suffix = "fc"

        # List files in the S3 directory
        s3_prefix = f"{self.source_bucket}/{date_str}/{cycle_str}z/ifs/{self.resolution}/{product_name}/"

        try:
            fs = fsspec.filesystem("s3", anon=True)
            all_files = fs.ls(s3_prefix)
        except Exception as e:
            # If listing fails, fall back to generating expected files
            import logging

            logging.warning(f"Failed to list S3 files, falling back to generation: {e}")
            return self._generate_s3_files(
                date_str, cycle_str, product_type, product_name, product_suffix
            )

        # Parse lead times from filenames
        # Pattern: YYYYMMDDHHmmss-Lh-product-suffix.grib2
        pattern = re.compile(
            rf"{date_str}{cycle_str}0000-(\d+)h-{product_name}-{product_suffix}\.grib2$"
        )

        files = []
        for file_path in all_files:
            filename = file_path.split("/")[-1]
            match = pattern.match(filename)
            if match:
                lead_time = int(match.group(1))

                # Only include files up to max_lead_time
                if lead_time <= self.max_lead_time:
                    lead_str = f"{lead_time:03d}"

                    source_path = f"s3://{file_path}"

                    # Destination path
                    if self.destination_bucket:
                        dest_path = (
                            f"gs://{self.destination_bucket}/{self.destination_prefix}"
                            f"ecmwf/{product_type}/{self.resolution}/{date_str}/{cycle_str}/"
                            f"ecmwf.{product_type}.{cycle_str}z.{self.resolution}.f{lead_str}.grib"
                        )
                    else:
                        dest_path = (
                            f"{self.local_download_dir}/ecmwf/{product_type}/{self.resolution}/"
                            f"{date_str}/{cycle_str}/"
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

        # Sort by lead time
        files.sort(key=lambda x: x.lead_time)
        return files

    def _generate_s3_files(
        self,
        date_str: str,
        cycle_str: str,
        product_type: str,
        product_name: str,
        product_suffix: str,
    ) -> List[GribFileSpec]:
        """Generate S3 file list using expected lead times (fallback)."""
        files = []
        for lead_time in self._generate_lead_times():
            lead_str = f"{lead_time:03d}"

            source_path = (
                f"s3://{self.source_bucket}/{date_str}/{cycle_str}z/ifs/{self.resolution}/{product_name}/"
                f"{date_str}{cycle_str}0000-{lead_time}h-{product_name}-{product_suffix}.grib2"
            )

            if self.destination_bucket:
                dest_path = (
                    f"gs://{self.destination_bucket}/{self.destination_prefix}"
                    f"ecmwf/{product_type}/{self.resolution}/{date_str}/{cycle_str}/"
                    f"ecmwf.{product_type}.{cycle_str}z.{self.resolution}.f{lead_str}.grib"
                )
            else:
                dest_path = (
                    f"{self.local_download_dir}/ecmwf/{product_type}/{self.resolution}/"
                    f"{date_str}/{cycle_str}/"
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

    def _discover_gcs_official_files(
        self, date_str: str, cycle_str: str, product_type: str
    ) -> List[GribFileSpec]:
        """Discover available files from official GCS bucket (gs://ecmwf-open-data)."""
        import fsspec
        import re

        if self.is_ensemble:
            product_name = "enfo"
            product_suffix = "ef"
        else:
            product_name = "oper"
            product_suffix = "fc"

        # List files in the GCS directory
        # Pattern: gs://ecmwf-open-data/YYYYMMDD/HHz/ifs/0p25/oper/
        gcs_prefix = f"{self.source_bucket}/{date_str}/{cycle_str}z/ifs/{self.resolution}/{product_name}/"

        try:
            fs = fsspec.filesystem("gs")
            all_files = fs.ls(gcs_prefix)
        except Exception as e:
            # If listing fails, fall back to generating expected files
            import logging

            logging.warning(
                f"Failed to list GCS files, falling back to generation: {e}"
            )
            return self._generate_gcs_official_files(
                date_str, cycle_str, product_type, product_name, product_suffix
            )

        # Parse lead times from filenames
        # Pattern: YYYYMMDDHHmmss-Lh-product-suffix.grib2
        pattern = re.compile(
            rf"{date_str}{cycle_str}0000-(\d+)h-{product_name}-{product_suffix}\.grib2$"
        )

        files = []
        for file_path in all_files:
            filename = file_path.split("/")[-1]
            match = pattern.match(filename)
            if match:
                lead_time = int(match.group(1))

                # Only include files up to max_lead_time
                if lead_time <= self.max_lead_time:
                    lead_str = f"{lead_time:03d}"

                    source_path = f"gs://{file_path}"

                    # Destination path
                    if self.destination_bucket:
                        dest_path = (
                            f"gs://{self.destination_bucket}/{self.destination_prefix}"
                            f"ecmwf/{product_type}/{self.resolution}/{date_str}/{cycle_str}/"
                            f"ecmwf.{product_type}.{cycle_str}z.{self.resolution}.f{lead_str}.grib"
                        )
                    else:
                        dest_path = (
                            f"{self.local_download_dir}/ecmwf/{product_type}/{self.resolution}/"
                            f"{date_str}/{cycle_str}/"
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

        # Sort by lead time
        files.sort(key=lambda x: x.lead_time)
        return files

    def _generate_gcs_official_files(
        self,
        date_str: str,
        cycle_str: str,
        product_type: str,
        product_name: str,
        product_suffix: str,
    ) -> List[GribFileSpec]:
        """Generate GCS official file list using expected lead times (fallback)."""
        files = []
        for lead_time in self._generate_lead_times():
            lead_str = f"{lead_time:03d}"

            # Pattern: gs://ecmwf-open-data/YYYYMMDD/HHz/ifs/0p25/oper/YYYYMMDDHHmmss-Lh-oper-fc.grib2
            source_path = (
                f"gs://{self.source_bucket}/{date_str}/{cycle_str}z/ifs/{self.resolution}/{product_name}/"
                f"{date_str}{cycle_str}0000-{lead_time}h-{product_name}-{product_suffix}.grib2"
            )

            if self.destination_bucket:
                dest_path = (
                    f"gs://{self.destination_bucket}/{self.destination_prefix}"
                    f"ecmwf/{product_type}/{self.resolution}/{date_str}/{cycle_str}/"
                    f"ecmwf.{product_type}.{cycle_str}z.{self.resolution}.f{lead_str}.grib"
                )
            else:
                dest_path = (
                    f"{self.local_download_dir}/ecmwf/{product_type}/{self.resolution}/"
                    f"{date_str}/{cycle_str}/"
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
        """
        Generate lead times for ECMWF with variable intervals.

        ECMWF Ensemble (ENS):
        - 0-144h: 3-hourly (0, 3, 6, ..., 144)
        - 144-360h: 6-hourly (150, 156, ..., 360)

        ECMWF HRES:
        - 0-90h: hourly (0, 1, 2, ..., 90)
        - 90-240h: 3-hourly (93, 96, ..., 240)

        Returns:
            List of lead times in hours
        """
        if self.is_ensemble:
            # Ensemble: 3-hourly up to 144h, then 6-hourly up to 360h
            if self.max_lead_time <= 144:
                return list(range(0, self.max_lead_time + 1, 3))
            else:
                # 3-hourly up to 144h
                lead_times = list(range(0, 145, 3))
                # 6-hourly from 150h onwards
                lead_times.extend(range(150, min(self.max_lead_time + 1, 361), 6))
                return lead_times
        else:
            # HRES: hourly up to 90h, then 3-hourly up to 240h
            if self.max_lead_time <= 90:
                return list(range(0, self.max_lead_time + 1, 1))
            else:
                # Hourly up to 90h
                lead_times = list(range(0, 91, 1))
                # 3-hourly from 93h onwards
                lead_times.extend(range(93, min(self.max_lead_time + 1, 241), 3))
                return lead_times

    def get_next_lead_time(self) -> int:
        """Get the next lead time after max_lead_time for validation.

        For sources where we discover files dynamically, we can't predict
        the next lead time. Return None to skip validation file check.
        """
        if self.source_type == "aws":
            # For AWS S3, we discover files dynamically - no validation file needed
            return None
        elif self.source_type == "gcs":
            # For GCS official bucket, we also discover files dynamically
            return None

        # For GCS mirrors, use the old logic
        if self.is_ensemble:
            # ENS: 3h up to 144h, then 6h
            if self.max_lead_time < 144:
                return min(self.max_lead_time + 3, 144)
            elif self.max_lead_time == 144:
                return 150  # First 6-hourly step
            elif self.max_lead_time < 360:
                return min(self.max_lead_time + 6, 360)
            else:
                return None
        else:
            # HRES: 1h up to 90h, then 3h
            if self.max_lead_time < 90:
                return min(self.max_lead_time + 1, 90)
            elif self.max_lead_time == 90:
                return 93  # First 3-hourly step
            elif self.max_lead_time < 240:
                return min(self.max_lead_time + 3, 240)
            else:
                return None


def create_data_source(
    product: str,
    resolution: str,
    cycle: datetime,
    max_lead_time: int,
    source_bucket: str,
    destination_bucket: str,
    destination_prefix: str = "",
    local_download_dir: str = None,
    source_type: str = None,
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
            source_type=source_type,
        )
    else:
        raise ValueError(f"Unknown product: {product}")
