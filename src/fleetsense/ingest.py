"""Idempotent data ingestion for NYC TLC Yellow Taxi Parquet files.

Downloads monthly Parquet files and the taxi zone lookup CSV, verifies
integrity (HTTP status, file size, readable Parquet footer), and tracks
ingested files in a metadata table so re-running adds 0 rows.

Implements: FR-1.01, AC-1.1
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pyarrow.parquet as pq
from tqdm import tqdm

from fleetsense.config import (
    DATA_MONTHS,
    DATA_YEAR,
    QUALITY_REPORTS_DIR,
    RAW_DIR,
    REFERENCE_DIR,
    TLC_BASE_URL,
    ZONE_LOOKUP_URL,
)

logger = logging.getLogger(__name__)


def _parquet_url(year: int, month: int) -> str:
    """Build the TLC download URL for a given year-month."""
    return f"{TLC_BASE_URL}/yellow_tripdata_{year}-{month:02d}.parquet"


def _verify_parquet(path: Path) -> int:
    """Verify a Parquet file is readable and return its row count.

    Raises ValueError if the file is corrupt or empty.
    """
    try:
        pf = pq.ParquetFile(path)
        row_count = pf.metadata.num_rows
        if row_count == 0:
            raise ValueError(f"Parquet file has 0 rows: {path}")
        return row_count
    except Exception as exc:
        raise ValueError(f"Failed to read Parquet file {path}: {exc}") from exc


def _download_file(url: str, dest: Path, *, timeout: float = 120.0) -> None:
    """Download a file with progress bar and integrity checks."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))

        with (
            open(dest, "wb") as f,
            tqdm(total=total, unit="B", unit_scale=True, desc=dest.name) as bar,
        ):
            for chunk in resp.iter_bytes(chunk_size=8192):
                f.write(chunk)
                bar.update(len(chunk))

    if dest.stat().st_size == 0:
        dest.unlink()
        raise RuntimeError(f"Downloaded file is empty: {url}")


def _load_ingestion_log() -> dict[str, dict]:
    """Load the ingestion metadata log (tracks which files have been ingested)."""
    log_path = QUALITY_REPORTS_DIR / "ingestion_meta.json"
    if log_path.exists():
        return json.loads(log_path.read_text())
    return {}


def _save_ingestion_log(meta: dict[str, dict]) -> None:
    """Persist the ingestion metadata log."""
    log_path = QUALITY_REPORTS_DIR / "ingestion_meta.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(meta, indent=2, default=str))


def download_zone_lookup() -> Path:
    """Download the taxi zone lookup CSV if not already present."""
    dest = REFERENCE_DIR / "taxi_zone_lookup.csv"
    if dest.exists() and dest.stat().st_size > 0:
        logger.info("Zone lookup already exists: %s", dest)
        return dest

    logger.info("Downloading taxi zone lookup â†’ %s", dest)
    _download_file(ZONE_LOOKUP_URL, dest)
    logger.info("Zone lookup saved (%d bytes)", dest.stat().st_size)
    return dest


def download_month(year: int, month: int) -> Path | None:
    """Download a single month's Parquet file (idempotent).

    Returns the file path if newly downloaded, or None if already ingested.
    """
    meta = _load_ingestion_log()
    key = f"yellow_tripdata_{year}-{month:02d}"
    dest = RAW_DIR / f"{key}.parquet"

    # Already ingested and verified
    if key in meta and dest.exists():
        logger.info("Already ingested: %s (%d rows)", key, meta[key]["row_count"])
        return None

    url = _parquet_url(year, month)
    logger.info("Downloading %s â†’ %s", url, dest)
    _download_file(url, dest)

    # Verify integrity
    row_count = _verify_parquet(dest)
    logger.info("Verified %s: %d rows", dest.name, row_count)

    # Record in metadata
    meta[key] = {
        "file": str(dest),
        "row_count": row_count,
        "downloaded_at": datetime.now(UTC).isoformat(),
        "url": url,
        "size_bytes": dest.stat().st_size,
    }
    _save_ingestion_log(meta)

    return dest


def ingest_all(year: int | None = None, months: list[int] | None = None) -> None:
    """Download all monthly files and the zone lookup (idempotent).

    Args:
        year: Data year (default: config.DATA_YEAR).
        months: List of months 1-12 (default: config.DATA_MONTHS).
    """
    year = year or DATA_YEAR
    months = months or DATA_MONTHS

    logger.info("Starting ingestion for %d months of %d", len(months), year)

    # Zone lookup first
    download_zone_lookup()

    # Monthly files
    new_count = 0
    for m in months:
        result = download_month(year, m)
        if result is not None:
            new_count += 1

    logger.info(
        "Ingestion complete: %d new files downloaded, %d already present",
        new_count,
        len(months) - new_count,
    )
