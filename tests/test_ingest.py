"""Unit tests for FleetSense data ingestion and idempotency (FR-1.01, AC-1.1)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from fleetsense.ingest import (
    _parquet_url,
    _verify_parquet,
    download_month,
)


def test_parquet_url():
    """Verify correct URL structure for TLC Yellow Taxi Parquet files."""
    url = _parquet_url(2024, 1)
    assert url == "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet"

    url_dec = _parquet_url(2024, 12)
    assert (
        url_dec == "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-12.parquet"
    )


def test_verify_parquet(tmp_path: Path):
    """Verify reading valid Parquet file returns exact row count."""
    table = pa.Table.from_arrays([pa.array([1, 2, 3])], names=["col1"])
    fpath = tmp_path / "test.parquet"
    pq.write_table(table, fpath)

    rows = _verify_parquet(fpath)
    assert rows == 3


def test_verify_empty_parquet_raises(tmp_path: Path):
    """Verify empty parquet table raises ValueError."""
    table = pa.Table.from_arrays([pa.array([], type=pa.int64())], names=["col1"])
    fpath = tmp_path / "empty.parquet"
    pq.write_table(table, fpath)

    with pytest.raises(ValueError, match="0 rows"):
        _verify_parquet(fpath)


def test_ingestion_idempotency(tmp_path: Path):
    """Verify that calling download_month on an already-ingested month is a no-op (AC-1.1)."""
    raw_dir = tmp_path / "raw"
    quality_dir = tmp_path / "quality_reports"
    raw_dir.mkdir(parents=True)
    quality_dir.mkdir(parents=True)

    key = "yellow_tripdata_2024-01"
    raw_file = raw_dir / f"{key}.parquet"
    table = pa.Table.from_arrays([pa.array([10, 20])], names=["val"])
    pq.write_table(table, raw_file)

    meta_file = quality_dir / "ingestion_meta.json"
    meta_file.write_text(
        json.dumps(
            {
                key: {
                    "file": str(raw_file),
                    "row_count": 2,
                    "downloaded_at": "2024-01-01T00:00:00Z",
                    "size_bytes": raw_file.stat().st_size,
                }
            }
        )
    )

    with (
        patch("fleetsense.ingest.RAW_DIR", raw_dir),
        patch("fleetsense.ingest.QUALITY_REPORTS_DIR", quality_dir),
    ):
        result = download_month(2024, 1)

    # Must return None without downloading
    assert result is None
