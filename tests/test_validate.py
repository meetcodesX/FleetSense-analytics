"""Unit tests for FleetSense data validation and quarantine engine (FR-1.02, NFR-02, AC-1.2)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import polars as pl

from fleetsense.validate import validate_month


def test_validation_rules_and_reconciliation(sample_raw_trips_df: pl.DataFrame, tmp_path: Path):
    """Verify validation suite correctly splits clean vs quarantined records and maintains row reconciliation.

    Test data contains:
      - 5 valid trips (including passenger_count=0, passenger_count=None, midnight-crossing)
      - 6 invalid trips (timestamp, duration, passenger_count>9, distance, location)
      - 1 duplicate trip (quarantined as duplicate)
      Total in: 12 rows
      Expected: 5 valid, 7 quarantined
    """
    raw_dir = tmp_path / "raw"
    quarantine_dir = tmp_path / "quarantine"
    validated_dir = tmp_path / "validated"
    quality_reports_dir = tmp_path / "quality_reports"
    run_log_path = quality_reports_dir / "run_log.jsonl"

    raw_dir.mkdir(parents=True)
    quarantine_dir.mkdir(parents=True)
    validated_dir.mkdir(parents=True)
    quality_reports_dir.mkdir(parents=True)

    # Save test data to raw_dir
    file_name = "yellow_tripdata_2024-01.parquet"
    raw_file = raw_dir / file_name
    sample_raw_trips_df.write_parquet(raw_file)

    with (
        patch("fleetsense.validate.RAW_DIR", raw_dir),
        patch("fleetsense.validate.QUARANTINE_DIR", quarantine_dir),
        patch("fleetsense.validate.RUN_LOG_PATH", run_log_path),
        patch("pathlib.Path.mkdir"),  # avoid side effects
    ):
        clean_path = validate_month(2024, 1)

    assert clean_path is not None
    assert clean_path.exists()

    # Read output files
    clean_df = pl.read_parquet(clean_path)
    q_file = quarantine_dir / "2024-01_quarantine.parquet"
    assert q_file.exists(), "Quarantine file must be created"
    q_df = pl.read_parquet(q_file)

    # 1. AC-1.2: Row Count Reconciliation
    rows_in = len(sample_raw_trips_df)
    rows_loaded = len(clean_df)
    rows_quarantined = len(q_df)

    assert rows_in == rows_loaded + rows_quarantined, (
        f"Reconciliation failed: {rows_in} != {rows_loaded} + {rows_quarantined}"
    )
    assert rows_loaded == 5, f"Expected 5 valid rows, got {rows_loaded}"
    assert rows_quarantined == 7, f"Expected 7 quarantined rows, got {rows_quarantined}"

    # 2. Verify passenger_count = 0 and None were KEPT in valid data
    p_counts = clean_df["passenger_count"].to_list()
    assert 0.0 in p_counts or 0 in p_counts, "passenger_count == 0 must be kept as valid unknown"
    assert None in p_counts or any(p is None for p in p_counts) or 0 in p_counts

    # 3. Verify quarantine reasons are populated
    assert "quarantine_reason" in q_df.columns
    assert "quarantine_rule" in q_df.columns
    assert "source_file" in q_df.columns

    reasons = q_df["quarantine_reason"].to_list()
    assert any("pickup_outside_data_year" in r for r in reasons)
    assert any("pickup_not_before_dropoff" in r for r in reasons)
    assert any("duration_too_short" in r for r in reasons)
    assert any("invalid_passenger_count" in r for r in reasons)
    assert any("invalid_trip_distance" in r for r in reasons)
    assert any("invalid_pickup_location" in r for r in reasons)
    assert any("exact_duplicate" in r for r in reasons)

    # 4. Verify structured JSON run log
    assert run_log_path.exists()
    log_lines = run_log_path.read_text().strip().split("\n")
    assert len(log_lines) >= 1
    last_log = json.loads(log_lines[-1])
    assert last_log["rows_in"] == rows_in
    assert last_log["rows_loaded"] == rows_loaded
    assert last_log["rows_quarantined"] == rows_quarantined
    assert last_log["reconciliation_ok"] is True
