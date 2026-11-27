"""Data validation and quarantine engine.

Validates raw Parquet files using pandera + deterministic rules,
quarantines invalid rows with reason codes, and produces structured
run logs with row-count reconciliation.

Implements: FR-1.02, NFR-02, AC-1.2
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from fleetsense.config import (
    DATA_END_DATE,
    DATA_START_DATE,
    DATA_YEAR,
    MAX_FARE_AMOUNT,
    MAX_LOCATION_ID,
    MAX_PASSENGER_COUNT,
    MAX_TOTAL_AMOUNT,
    MAX_TRIP_DISTANCE_MILES,
    MAX_TRIP_DURATION_MINUTES,
    MIN_LOCATION_ID,
    MIN_TRIP_DURATION_MINUTES,
    QUARANTINE_DIR,
    RAW_DIR,
    RUN_LOG_PATH,
)

logger = logging.getLogger(__name__)


def _append_run_log(entry: dict) -> None:
    """Append a structured JSON entry to the run log."""
    RUN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RUN_LOG_PATH, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def validate_month(year: int, month: int) -> Path | None:
    """Validate a single month's raw data and quarantine invalid rows.

    Returns the path to the validated (clean) Parquet file, or None on error.

    Every row is accounted for: rows_in == rows_loaded + rows_quarantined.
    Quarantined rows include reason codes in quarantine_reason and quarantine_rule.
    """
    source_file = f"yellow_tripdata_{year}-{month:02d}.parquet"
    raw_path = RAW_DIR / source_file

    if not raw_path.exists():
        logger.error("Raw file not found: %s", raw_path)
        return None

    logger.info("Validating %s", source_file)

    # Read raw data with Polars (memory-efficient, single month at a time)
    df = pl.read_parquet(raw_path)
    rows_in = len(df)
    logger.info("  Rows in: %d", rows_in)
    # Compute derived columns needed for validation
    df = df.with_columns(
        # Trip duration in minutes
        (
            (pl.col("tpep_dropoff_datetime") - pl.col("tpep_pickup_datetime")).dt.total_seconds()
            / 60.0
        ).alias("trip_duration_minutes"),
    )
    # Apply validation rules â€” build a quarantine_reason column
    # Each rule appends a reason; rows with any reason are quarantined.
    reasons: list[pl.Expr] = []

    # R01: Pickup datetime within data year
    reasons.append(
        pl.when(
            (pl.col("tpep_pickup_datetime") < pl.lit(DATA_START_DATE).str.to_datetime())
            | (pl.col("tpep_pickup_datetime") >= pl.lit(DATA_END_DATE).str.to_datetime())
        )
        .then(pl.lit("pickup_outside_data_year"))
        .otherwise(pl.lit(None))
        .alias("r01")
    )

    # R02: Dropoff datetime within data year
    reasons.append(
        pl.when(
            (pl.col("tpep_dropoff_datetime") < pl.lit(DATA_START_DATE).str.to_datetime())
            | (pl.col("tpep_dropoff_datetime") >= pl.lit(DATA_END_DATE).str.to_datetime())
        )
        .then(pl.lit("dropoff_outside_data_year"))
        .otherwise(pl.lit(None))
        .alias("r02")
    )

    # R03: Pickup before dropoff
    reasons.append(
        pl.when(pl.col("tpep_pickup_datetime") >= pl.col("tpep_dropoff_datetime"))
        .then(pl.lit("pickup_not_before_dropoff"))
        .otherwise(pl.lit(None))
        .alias("r03")
    )

    # R04: Trip duration >= 1 minute
    reasons.append(
        pl.when(pl.col("trip_duration_minutes") < MIN_TRIP_DURATION_MINUTES)
        .then(pl.lit("duration_too_short"))
        .otherwise(pl.lit(None))
        .alias("r04")
    )

    # R05: Trip duration <= 240 minutes
    reasons.append(
        pl.when(pl.col("trip_duration_minutes") > MAX_TRIP_DURATION_MINUTES)
        .then(pl.lit("duration_too_long"))
        .otherwise(pl.lit(None))
        .alias("r05")
    )

    # R06: Passenger count not negative and not > 9
    # (0 and NULL are kept as "unknown")
    reasons.append(
        pl.when((pl.col("passenger_count") < 0) | (pl.col("passenger_count") > MAX_PASSENGER_COUNT))
        .then(pl.lit("invalid_passenger_count"))
        .otherwise(pl.lit(None))
        .alias("r06")
    )

    # R07: Trip distance > 0 and <= 200
    reasons.append(
        pl.when(
            (pl.col("trip_distance") <= 0) | (pl.col("trip_distance") > MAX_TRIP_DISTANCE_MILES)
        )
        .then(pl.lit("invalid_trip_distance"))
        .otherwise(pl.lit(None))
        .alias("r07")
    )

    # R08: Fare amount in [0, 500]
    reasons.append(
        pl.when((pl.col("fare_amount") < 0) | (pl.col("fare_amount") > MAX_FARE_AMOUNT))
        .then(pl.lit("invalid_fare_amount"))
        .otherwise(pl.lit(None))
        .alias("r08")
    )

    # R09: Total amount in [0, 1000]
    reasons.append(
        pl.when((pl.col("total_amount") < 0) | (pl.col("total_amount") > MAX_TOTAL_AMOUNT))
        .then(pl.lit("invalid_total_amount"))
        .otherwise(pl.lit(None))
        .alias("r09")
    )

    # R10: Valid pickup location ID
    reasons.append(
        pl.when(
            (pl.col("PULocationID") < MIN_LOCATION_ID) | (pl.col("PULocationID") > MAX_LOCATION_ID)
        )
        .then(pl.lit("invalid_pickup_location"))
        .otherwise(pl.lit(None))
        .alias("r10")
    )

    # R11: Valid dropoff location ID
    reasons.append(
        pl.when(
            (pl.col("DOLocationID") < MIN_LOCATION_ID) | (pl.col("DOLocationID") > MAX_LOCATION_ID)
        )
        .then(pl.lit("invalid_dropoff_location"))
        .otherwise(pl.lit(None))
        .alias("r11")
    )

    # Apply all reason columns
    reason_cols = [f"r{i:02d}" for i in range(1, 12)]
    df = df.with_columns(reasons)

    # Combine reasons into a single pipe-delimited string
    df = df.with_columns(
        pl.concat_str(
            [pl.col(c) for c in reason_cols],
            separator="|",
            ignore_nulls=True,
        ).alias("quarantine_reason")
    )
    # R12: Exact duplicate detection (keep first occurrence, quarantine duplicates)
    original_cols = [c for c in df.columns if c not in reason_cols and c != "quarantine_reason"]
    dup_mask = pl.col(original_cols[0]).cum_count().over(original_cols) > 1
    df = df.with_columns(
        pl.when(dup_mask & (pl.col("quarantine_reason") == ""))
        .then(pl.lit("exact_duplicate"))
        .when(dup_mask & (pl.col("quarantine_reason") != ""))
        .then(pl.col("quarantine_reason") + pl.lit("|exact_duplicate"))
        .otherwise(pl.col("quarantine_reason"))
        .alias("quarantine_reason")
    )
    # Split into valid and quarantine sets
    is_invalid = pl.col("quarantine_reason") != ""

    quarantine_df = df.filter(is_invalid).with_columns(
        pl.lit(source_file).alias("source_file"),
        # Extract the first rule that fired for quarantine_rule
        pl.col("quarantine_reason").str.split("|").list.first().alias("quarantine_rule"),
    )
    # Drop intermediate reason columns from quarantine output
    quarantine_df = quarantine_df.drop(reason_cols)

    valid_df = df.filter(~is_invalid).drop(reason_cols + ["quarantine_reason"])

    rows_loaded = len(valid_df)
    rows_quarantined = len(quarantine_df)
    # Reconciliation check: rows_in == rows_loaded + rows_quarantined
    assert rows_in == rows_loaded + rows_quarantined, (
        f"Row count mismatch: {rows_in} != {rows_loaded} + {rows_quarantined}"
    )

    logger.info(
        "  Valid: %d | Quarantined: %d (%.1f%%)",
        rows_loaded,
        rows_quarantined,
        100.0 * rows_quarantined / rows_in if rows_in > 0 else 0,
    )
    # Write outputs
    # Save validated data
    validated_dir = RAW_DIR.parent / "validated"
    validated_dir.mkdir(parents=True, exist_ok=True)
    validated_path = validated_dir / source_file
    valid_df.write_parquet(validated_path)

    # Save quarantine
    if rows_quarantined > 0:
        QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
        q_path = QUARANTINE_DIR / f"{year}-{month:02d}_quarantine.parquet"
        quarantine_df.write_parquet(q_path)
        logger.info("  Quarantine written: %s", q_path)
    # Append structured run log entry
    log_entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "stage": "validate",
        "source_file": source_file,
        "year": year,
        "month": month,
        "rows_in": rows_in,
        "rows_loaded": rows_loaded,
        "rows_quarantined": rows_quarantined,
        "quarantine_pct": round(100.0 * rows_quarantined / rows_in, 2) if rows_in else 0,
        "reconciliation_ok": rows_in == rows_loaded + rows_quarantined,
    }
    _append_run_log(log_entry)

    return validated_path


def validate_all(year: int | None = None, months: list[int] | None = None) -> None:
    """Validate all monthly files sequentially."""
    from fleetsense.config import DATA_MONTHS

    year = year or DATA_YEAR
    months = months or DATA_MONTHS

    logger.info("Starting validation for %d months of %d", len(months), year)

    for m in months:
        validate_month(year, m)

    logger.info("Validation complete for all %d months", len(months))
