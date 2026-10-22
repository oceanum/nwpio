#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["typer>=0.12", "google-cloud-storage", "pandas"]
# ///
"""
Analyse when ECMWF open data cycles become complete in gs://ecmwf-open-data.

For each cycle, the completion delay is the time between the cycle time and the
creation of the last GRIB file needed (all lead times up to --max-lead-time).
This is the earliest time a pipeline processing that cycle can succeed, so it
is what the prax cron delay must cover.

Usage:

# 0.1 deg surface files since the 0.1 deg feed started
uv run scripts/ecmwf_upload_delay.py 0p1 --file-type sfc --start-date 20261020

# 0.25 deg files over a longer period, compared with a 9h30m cron delay
uv run scripts/ecmwf_upload_delay.py 0p25 --start-date 20260601 --cron-delay 9.5
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Annotated
import re

import pandas as pd
import typer
from google.cloud import storage


class FileType(str, Enum):
    sfc = "sfc"
    pl = "pl"


def expected_lead_times(max_lead_time: int) -> list[int]:
    """ECMWF open data steps: 3-hourly to 144h, then 6-hourly to 360h."""
    steps = list(range(0, 145, 3)) + list(range(150, 361, 6))
    return [lt for lt in steps if lt <= max_lead_time]


def cycle_stats(
    client: storage.Client,
    bucket: str,
    cycle: datetime,
    resolution: str,
    stream: str,
    file_type: FileType | None,
    max_lead_time: int,
) -> dict:
    """Return creation-time statistics for the GRIB files of one cycle."""
    prefix = f"{cycle:%Y%m%d}/{cycle:%H}z/ifs/{resolution}/{stream}/"
    suffix = f"-{file_type.value}" if file_type else ""
    pattern = re.compile(rf"{cycle:%Y%m%d%H}0000-(\d+)h-{stream}-\w+{suffix}\.grib2$")
    created = {}
    for blob in client.list_blobs(bucket, prefix=prefix, fields="items(name,timeCreated),nextPageToken"):
        match = pattern.search(blob.name)
        if match and int(match.group(1)) <= max_lead_time:
            created[int(match.group(1))] = blob.time_created

    expected = expected_lead_times(max_lead_time)
    missing = [lt for lt in expected if lt not in created]
    row = {"cycle": cycle, "hour": f"{cycle:%H}z", "nfiles": len(created), "nmissing": len(missing)}
    if created:
        hours = lambda t: (t - cycle).total_seconds() / 3600  # noqa: E731
        row["first_h"] = hours(min(created.values()))
        row["complete_h"] = hours(max(created.values())) if not missing else None
    return row


def main(
    resolution: Annotated[str, typer.Argument(help="Resolution directory, e.g. 0p1 or 0p25")],
    start_date: Annotated[str, typer.Option(help="First cycle date, YYYYMMDD")],
    end_date: Annotated[str | None, typer.Option(help="Last cycle date, YYYYMMDD (default: today)")] = None,
    file_type: Annotated[FileType | None, typer.Option(help="0p1 split file to check: sfc or pl")] = None,
    stream: Annotated[str, typer.Option(help="Stream directory, e.g. oper or enfo")] = "oper",
    cycles: Annotated[list[str], typer.Option("--cycle", help="Cycle hours to check, repeatable")] = ["00", "12"],
    max_lead_time: Annotated[int, typer.Option(help="Last lead time the pipeline needs, hours")] = 240,
    cron_delay: Annotated[float | None, typer.Option(help="Configured cron delay, hours, to compare against")] = None,
    bucket: Annotated[str, typer.Option(help="Source bucket")] = "ecmwf-open-data",
    workers: Annotated[int, typer.Option(help="Parallel cycle listings")] = 16,
    output: Annotated[Path | None, typer.Option(help="Optional CSV with one row per cycle")] = None,
):
    """Report how long after cycle time each ECMWF open data cycle is complete."""
    start = datetime.strptime(start_date, "%Y%m%d").replace(tzinfo=timezone.utc)
    end = (
        datetime.strptime(end_date, "%Y%m%d").replace(tzinfo=timezone.utc)
        if end_date
        else datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    )
    cycle_times = [
        start + timedelta(days=d, hours=int(h))
        for d in range((end - start).days + 1)
        for h in cycles
    ]
    client = storage.Client.create_anonymous_client()
    with ThreadPoolExecutor(workers) as pool:
        rows = list(
            pool.map(
                lambda c: cycle_stats(client, bucket, c, resolution, stream, file_type, max_lead_time),
                cycle_times,
            )
        )
    df = pd.DataFrame(rows).sort_values("cycle")
    now = datetime.now(timezone.utc)
    # Ignore cycles that may still be in progress
    df = df[df.cycle < now - timedelta(hours=12)]
    absent = df[df.nfiles == 0]
    incomplete = df[(df.nfiles > 0) & (df.nmissing > 0)]
    df_ok = df.dropna(subset=["complete_h"])

    label = f"{resolution}{'-' + file_type.value if file_type else ''} {stream}"
    typer.echo(f"{label}, lead times 0-{max_lead_time}h, cycles {df.cycle.min():%Y-%m-%d %Hz} to {df.cycle.max():%Y-%m-%d %Hz}")
    typer.echo(f"  cycles: {len(df)} checked, {len(df_ok)} complete, {len(incomplete)} incomplete, {len(absent)} absent")
    for _, r in incomplete.iterrows():
        typer.echo(f"  incomplete: {r.cycle:%Y-%m-%d %Hz} ({r.nmissing} lead times missing)")
    for _, r in absent.iterrows():
        typer.echo(f"  absent: {r.cycle:%Y-%m-%d %Hz}")

    def fmt(h):
        return f"{int(h)}h{round(h % 1 * 60):02d}m"

    typer.echo("  completion delay (last file created - cycle time):")
    for hour, g in [("all", df_ok), *df_ok.groupby("hour")]:
        d = g.complete_h
        line = (
            f"    {hour:>4}: n={len(d):4d}  min={fmt(d.min())}  median={fmt(d.median())}  "
            f"p95={fmt(d.quantile(0.95))}  max={fmt(d.max())}"
        )
        if cron_delay is not None:
            line += f"  later than cron delay: {(d > cron_delay).sum()}"
        typer.echo(line)
    if cron_delay is not None:
        late = df_ok[df_ok.complete_h > cron_delay].sort_values("complete_h", ascending=False)
        for _, r in late.head(20).iterrows():
            typer.echo(f"  late: {r.cycle:%Y-%m-%d %Hz} complete at +{fmt(r.complete_h)}")
    if output:
        df.to_csv(output, index=False)
        typer.echo(f"Per-cycle results saved to {output}")


if __name__ == "__main__":
    typer.run(main)
