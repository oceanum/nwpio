"""Utility functions for NWP download."""

import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from google.cloud import storage

logger = logging.getLogger(__name__)


def parse_gcs_path(path: str) -> tuple[str, str]:
    """
    Parse GCS path into bucket and blob name.

    Args:
        path: GCS path (gs://bucket/path/to/file)

    Returns:
        Tuple of (bucket_name, blob_name)
    """
    parsed = urlparse(path)
    if parsed.scheme != "gs":
        raise ValueError(f"Not a GCS path: {path}")
    bucket = parsed.netloc
    blob = parsed.path.lstrip("/")
    return bucket, blob


def is_gcs_path(path: str) -> bool:
    """Check if path is a GCS path."""
    return path.startswith("gs://")


def ensure_local_dir(path: Path) -> None:
    """Ensure local directory exists."""
    path.mkdir(parents=True, exist_ok=True)


def get_gcs_client() -> storage.Client:
    """Get authenticated GCS client."""
    return storage.Client()


def gcs_blob_exists(
    bucket_name: str, blob_name: str, client: Optional[storage.Client] = None
) -> bool:
    """
    Check if a GCS blob exists.

    Args:
        bucket_name: GCS bucket name
        blob_name: Blob name (path within bucket)
        client: Optional GCS client

    Returns:
        True if blob exists, False otherwise
    """
    if client is None:
        client = get_gcs_client()

    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    return blob.exists()


def copy_gcs_blob(
    source_bucket: str,
    source_blob: str,
    dest_bucket: str,
    dest_blob: str,
    client: Optional[storage.Client] = None,
) -> bool:
    """
    Copy a blob from one GCS location to another.

    Args:
        source_bucket: Source bucket name
        source_blob: Source blob name
        dest_bucket: Destination bucket name
        dest_blob: Destination blob name
        client: Optional GCS client

    Returns:
        True if successful, False otherwise
    """
    if client is None:
        client = get_gcs_client()

    try:
        source_bucket_obj = client.bucket(source_bucket)
        source_blob_obj = source_bucket_obj.blob(source_blob)

        dest_bucket_obj = client.bucket(dest_bucket)

        # Copy the blob
        source_bucket_obj.copy_blob(source_blob_obj, dest_bucket_obj, dest_blob)
        return True

    except Exception as e:
        logger.error(
            f"Failed to copy {source_bucket}/{source_blob} to {dest_bucket}/{dest_blob}: {e}"
        )
        return False


def download_gcs_file(
    bucket_name: str,
    blob_name: str,
    local_path: Path,
    client: Optional[storage.Client] = None,
) -> bool:
    """
    Download a file from GCS to local filesystem.

    Args:
        bucket_name: GCS bucket name
        blob_name: Blob name
        local_path: Local file path
        client: Optional GCS client

    Returns:
        True if successful, False otherwise
    """
    if client is None:
        client = get_gcs_client()

    try:
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        # Ensure parent directory exists
        local_path.parent.mkdir(parents=True, exist_ok=True)

        blob.download_to_filename(str(local_path))
        return True

    except Exception as e:
        logger.error(f"Failed to download {bucket_name}/{blob_name}: {e}")
        return False


def upload_gcs_file(
    local_path: Path,
    bucket_name: str,
    blob_name: str,
    client: Optional[storage.Client] = None,
) -> bool:
    """
    Upload a local file to GCS.

    Args:
        local_path: Local file path
        bucket_name: GCS bucket name
        blob_name: Blob name
        client: Optional GCS client

    Returns:
        True if successful, False otherwise
    """
    if client is None:
        client = get_gcs_client()

    try:
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(local_path))
        return True

    except Exception as e:
        logger.error(f"Failed to upload {local_path} to {bucket_name}/{blob_name}: {e}")
        return False


def format_bytes(size: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"
