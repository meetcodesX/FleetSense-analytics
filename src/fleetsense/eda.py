"""Exploratory data analysis -- seasonality, zone ranking, anomalies, naive baseline.

Operates on analytical mart Parquet files. Findings are written to
docs/findings_report.md.

Implements: NFR-04 (naive baseline comparison), FR-1.08 (shift-split)
"""

from __future__ import annotations

import json
import logging

import polars as pl

from fleetsense.config import MARTS_DIR, QUALITY_REPORTS_DIR

logger = logging.getLogger(__name__)


def load_mart(name: str) -> pl.DataFrame:
    """Load a mart Parquet file by name."""
    path = MARTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Mart file not found: {path}")
    return pl.read_parquet(path)


# 1. Seasonality analysis
def analyze_seasonality() -> dict:
    """Analyze demand seasonality by hour-of-day, day-of-week, and month."""
    logger.info("Analyzing seasonality patterns...")

    hourly = load_mart("hourly_demand.parquet")
    monthly = load_mart("monthly_trips.parquet")

    # Hourly profile (across all zones)
    hourly_profile = (
        hourly.group_by(["hour_of_day", "shift"])
        .agg(
            pl.col("trip_count").sum().alias("total_trips"),
            pl.col("total_revenue").sum().alias("total_revenue"),
        )
        .sort("hour_of_day")
    )

    # Day-of-week profile
    dow_profile = (
        hourly.group_by("day_of_week")
        .agg(
            pl.col("trip_count").sum().alias("total_trips"),
            pl.col("total_revenue").sum().alias("total_revenue"),
        )
        .sort("day_of_week")
    )

    # Monthly totals (aggregate shifts)
    monthly_totals = (
        monthly.filter(pl.col("shift").is_not_null())
        .group_by("month")
        .agg(
            pl.col("trip_count").sum().alias("total_trips"),
            pl.col("total_revenue").sum().alias("total_revenue"),
        )
        .sort("month")
    )

    # Peak and trough
    peak_hour = hourly_profile.sort("total_trips", descending=True).row(0, named=True)
    trough_hour = (
        hourly_profile.filter(pl.col("total_trips") > 0).sort("total_trips").row(0, named=True)
    )

    return {
        "hourly_profile": hourly_profile.to_dicts(),
        "dow_profile": dow_profile.to_dicts(),
        "monthly_totals": monthly_totals.to_dicts(),
        "peak_hour": peak_hour,
        "trough_hour": trough_hour,
        "peak_to_trough_ratio": round(
            peak_hour["total_trips"] / max(trough_hour["total_trips"], 1), 1
        ),
    }


# 2. Zone ranking
def analyze_zones(top_n: int = 10) -> dict:
    """Rank zones by trip volume and revenue."""
    logger.info("Analyzing zone rankings...")

    zones = load_mart("zone_summary.parquet")

    # Aggregate across shifts for overall ranking
    zone_totals = (
        zones.group_by(["location_id", "borough", "zone"])
        .agg(
            pl.col("trip_count").sum().alias("total_trips"),
            pl.col("total_revenue").sum().alias("total_revenue"),
            pl.col("avg_fare").mean().alias("avg_fare"),
        )
        .sort("total_trips", descending=True)
    )

    top_zones = zone_totals.head(top_n).to_dicts()
    bottom_zones = (
        zone_totals.filter(pl.col("total_trips") > 0).sort("total_trips").head(top_n).to_dicts()
    )

    # Night-shift top zones
    night_zones = (
        zones.filter(pl.col("shift") == "Night")
        .sort("trip_count", descending=True)
        .head(top_n)
        .to_dicts()
    )

    return {
        "top_zones": top_zones,
        "bottom_zones": bottom_zones,
        "night_shift_top_zones": night_zones,
        "total_active_zones": len(zone_totals.filter(pl.col("total_trips") > 0)),
    }


# 3. Data anomalies
def analyze_anomalies() -> dict:
    """Summarize data quality anomalies found during validation."""
    logger.info("Analyzing data anomalies...")

    run_log_path = QUALITY_REPORTS_DIR / "run_log.jsonl"
    if not run_log_path.exists():
        return {"error": "run_log.jsonl not found"}

    entries = []
    with open(run_log_path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    # Keep only the latest run per month
    latest = {}
    for e in entries:
        key = e.get("source_file", "")
        latest[key] = e
    entries = list(latest.values())

    total_in = sum(e.get("rows_in", 0) for e in entries)
    total_loaded = sum(e.get("rows_loaded", 0) for e in entries)
    total_quarantined = sum(e.get("rows_quarantined", 0) for e in entries)
    all_reconciled = all(e.get("reconciliation_ok", False) for e in entries)

    # Month with highest quarantine rate
    worst_month = max(entries, key=lambda e: e.get("quarantine_pct", 0))

    return {
        "total_rows_in": total_in,
        "total_rows_loaded": total_loaded,
        "total_rows_quarantined": total_quarantined,
        "overall_quarantine_pct": round(100.0 * total_quarantined / max(total_in, 1), 2),
        "all_months_reconciled": all_reconciled,
        "worst_month": worst_month.get("source_file"),
        "worst_month_quarantine_pct": worst_month.get("quarantine_pct"),
        "anomalies_handled": [
            "passenger_count=0 or NULL kept as 'unknown' (not quarantined)",
            "Midnight-crossing trips retained (classified by pickup hour)",
            "Trips 60-240 minutes flagged but kept; >240 min quarantined",
            "trip_distance=0 quarantined (likely cancellations)",
            "Exact duplicate rows quarantined with reason code",
            "Timestamps outside 2024 quarantined",
        ],
    }


# 4. Naive baseline comparison (NFR-04)
def naive_baseline_comparison() -> dict:
    """Compare actual hourly demand against a naive same-hour-last-week baseline.

    Baseline: For each (zone, hour_of_day, day_of_week), predict the average
    demand from the first 8 months as the forecast for months 9-12.
    """
    logger.info("Computing naive baseline comparison (NFR-04)...")

    hourly = load_mart("hourly_demand.parquet")

    # Split: months 1-8 as "train", months 9-12 as "test"
    train = hourly.filter(pl.col("month") <= 8)
    test = hourly.filter(pl.col("month") > 8)

    # Baseline: average trip_count per (location_id, day_of_week, hour_of_day)
    baseline = (
        train.group_by(["location_id", "day_of_week", "hour_of_day"])
        .agg(pl.col("trip_count").mean().alias("baseline_pred"))
        .sort(["location_id", "day_of_week", "hour_of_day"])
    )

    # Join with test to compute errors
    test_with_baseline = test.join(
        baseline, on=["location_id", "day_of_week", "hour_of_day"], how="left"
    ).with_columns(pl.col("baseline_pred").fill_null(0.0))

    # Compute error metrics
    actual = test_with_baseline["trip_count"].cast(pl.Float64)
    predicted = test_with_baseline["baseline_pred"]

    errors = (actual - predicted).abs()
    mae = errors.mean()
    rmse = (errors.pow(2).mean()).sqrt()
    total_actual = actual.sum()
    total_error = errors.sum()
    wape = total_error / max(total_actual, 1) * 100.0

    return {
        "method": "Same hour-of-day + day-of-week average from months 1-8",
        "train_months": "Jan-Aug 2024",
        "test_months": "Sep-Dec 2024",
        "mae": round(mae, 2) if mae is not None else None,
        "rmse": round(rmse, 2) if rmse is not None else None,
        "wape_pct": round(wape, 2) if wape is not None else None,
        "interpretation": (
            "The naive baseline uses historical same-weekday-hour averages "
            "to predict future demand. This provides a floor for any ML model "
            "to beat in Phase 2."
        ),
    }


# 5. Shift analysis (FR-1.08 -- Halvorsen Dusk Rides)
def analyze_shifts() -> dict:
    """Compute shift-split metrics for the MetroCab / Halvorsen Dusk Rides client."""
    logger.info("Analyzing shift-split metrics (FR-1.08)...")

    kpis = load_mart("overview_kpis.parquet")
    zones = load_mart("zone_summary.parquet")

    # Overall shift split from ROLLUP KPIs
    shift_kpis = kpis.filter(pl.col("shift").is_not_null()).to_dicts()

    # Shift comparison by zone
    night_zones = (
        zones.filter(pl.col("shift") == "Night")
        .sort("trip_count", descending=True)
        .head(15)
        .to_dicts()
    )
    day_zones = (
        zones.filter(pl.col("shift") == "Day")
        .sort("trip_count", descending=True)
        .head(15)
        .to_dicts()
    )

    # Night share
    total_all = kpis.filter(pl.col("shift").is_null())["total_trips"][0]
    night_total = kpis.filter(pl.col("shift") == "Night")
    night_trips = night_total["total_trips"][0] if len(night_total) > 0 else 0
    night_share = round(100.0 * night_trips / max(total_all, 1), 2)

    return {
        "shift_kpis": shift_kpis,
        "night_shift_trip_share_pct": night_share,
        "night_top_zones": night_zones,
        "day_top_zones": day_zones,
        "recommendations": [
            f"Night shift accounts for {night_share}% of total trips.",
            "Consider reallocating driver availability towards Friday/Saturday night shifts.",
            "Top night-shift zones concentrate in entertainment and transit hub areas.",
        ],
    }


# Main EDA runner
def run_eda() -> dict:
    """Run all exploratory analyses and return combined findings."""
    logger.info("Running full EDA suite...")

    results = {
        "seasonality": analyze_seasonality(),
        "zones": analyze_zones(),
        "anomalies": analyze_anomalies(),
        "naive_baseline": naive_baseline_comparison(),
        "shift_analysis": analyze_shifts(),
    }

    logger.info("EDA complete.")
    return results


if __name__ == "__main__":
    import json as _json

    logging.basicConfig(level=logging.INFO)
    findings = run_eda()
    print(_json.dumps(findings, indent=2, default=str))
