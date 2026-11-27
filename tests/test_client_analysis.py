"""Unit tests for MetroCab client requirement analysis (FR-1.08, AC-1.5).

Client Requirement:
"Trips starting between 22:00 and 05:59 are a separate shift. Shift is a
calendar dimension column, and all hourly demand and metrics must be split by shift."
"""

from __future__ import annotations

import polars as pl

from fleetsense.client_analysis import (
    SHIFT_DAY,
    SHIFT_NIGHT,
    add_shift_column,
    classify_shift,
    compute_shift_hourly_profile,
    compute_shift_summary,
    run_client_analysis,
)


def test_classify_shift_hours():
    """Verify hours 22:00 through 05:59 are classified as Night, others as Day."""
    # Night hours: 22, 23, 0, 1, 2, 3, 4, 5
    for h in [22, 23, 0, 1, 2, 3, 4, 5]:
        assert classify_shift(h) == SHIFT_NIGHT, f"Hour {h} should be Night shift"

    # Day hours: 6 through 21
    for h in range(6, 22):
        assert classify_shift(h) == SHIFT_DAY, f"Hour {h} should be Day shift"


def test_add_shift_column():
    """Verify add_shift_column appends 'shift' correctly to a Polars DataFrame."""
    df = pl.DataFrame({"pickup_hour": [2, 10, 22, 18, 5, 6]})
    result = add_shift_column(df)

    assert "shift" in result.columns
    assert result["shift"].to_list() == [
        SHIFT_NIGHT,
        SHIFT_DAY,
        SHIFT_NIGHT,
        SHIFT_DAY,
        SHIFT_NIGHT,
        SHIFT_DAY,
    ]


def test_compute_shift_summary():
    """Verify shift summary aggregates trips and revenues and calculates percentage shares."""
    df = pl.DataFrame(
        {
            "pickup_hour": [2, 3, 10, 14, 16],  # 2 night, 3 day
            "total_amount": [20.0, 30.0, 15.0, 25.0, 10.0],  # night=50.0, day=50.0
            "fare_amount": [15.0, 22.0, 10.0, 18.0, 7.0],
            "tip_amount": [3.0, 5.0, 2.0, 4.0, 1.0],
            "tolls_amount": [0.0, 0.0, 0.0, 0.0, 0.0],
            "trip_distance": [4.0, 5.0, 2.0, 3.0, 1.5],
            "trip_duration_minutes": [15.0, 20.0, 10.0, 18.0, 8.0],
        }
    )

    summary = compute_shift_summary(df)

    assert len(summary) == 2
    night_row = summary.filter(pl.col("shift") == SHIFT_NIGHT)
    day_row = summary.filter(pl.col("shift") == SHIFT_DAY)

    assert night_row["trip_count"][0] == 2
    assert day_row["trip_count"][0] == 3
    assert night_row["trip_share_pct"][0] == 40.0
    assert day_row["trip_share_pct"][0] == 60.0
    assert night_row["total_revenue"][0] == 50.0
    assert day_row["total_revenue"][0] == 50.0


def test_compute_shift_hourly_profile():
    """Verify hourly profile groups by pickup_hour and shift."""
    df = pl.DataFrame(
        {
            "pickup_hour": [2, 2, 14, 14],
            "total_amount": [20.0, 30.0, 15.0, 25.0],
            "fare_amount": [15.0, 25.0, 10.0, 20.0],
        }
    )
    profile = compute_shift_hourly_profile(df)
    assert len(profile) == 2
    h2 = profile.filter(pl.col("pickup_hour") == 2)
    assert h2["trip_count"][0] == 2
    assert h2["shift"][0] == SHIFT_NIGHT


def test_run_client_analysis():
    """Verify end-to-end client analysis executes and returns expected structure."""
    df = pl.DataFrame(
        {
            "pickup_hour": [1, 23, 12, 15],
            "total_amount": [25.0, 35.0, 18.0, 22.0],
            "fare_amount": [18.0, 25.0, 12.0, 16.0],
            "tip_amount": [4.0, 6.0, 3.0, 3.0],
            "tolls_amount": [0.0, 0.0, 0.0, 0.0],
            "trip_distance": [5.0, 7.0, 2.5, 3.0],
            "trip_duration_minutes": [18.0, 25.0, 12.0, 15.0],
        }
    )
    result = run_client_analysis(df)
    assert result["status"] == "completed"
    assert "key_metrics" in result
    assert result["key_metrics"]["night_shift_trips"] == 2
    assert result["key_metrics"]["night_shift_trip_share_pct"] == 50.0
