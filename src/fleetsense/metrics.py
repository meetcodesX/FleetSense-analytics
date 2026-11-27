"""Canonical metric definitions for FleetSense.

Single source of truth for all KPI calculations (FR-1.04).
These names and formulas are mirrored in docs/data_dictionary.md,
sql/02_fact_trips.sql, and app/dashboard.py.

Revenue policy:
  - total_revenue = total_amount  (complete passenger charge)
  - Tolls are pass-through charges â€” NEVER labelled "driver earnings"
  - CR-1: report revenue with AND without tolls + surcharges
"""

from __future__ import annotations

# Column name constants (match Parquet / DuckDB column names)
FARE_REVENUE_COL = "fare_amount"
TIP_REVENUE_COL = "tip_amount"
TOLLS_REVENUE_COL = "tolls_amount"
TOTAL_REVENUE_COL = "total_amount"

SURCHARGE_COMPONENT_COLS: list[str] = [
    "extra",
    "mta_tax",
    "improvement_surcharge",
    "congestion_surcharge",
    "airport_fee",
]
# Derived metric names (used in SQL & marts)
SURCHARGES_REVENUE = "surcharges_revenue"
REVENUE_EXCL_TOLLS_SURCHARGES = "revenue_excl_tolls_surcharges"


# Python metric functions â€” usable in Polars expressions or plain floats
def compute_surcharges(
    extra: float,
    mta_tax: float,
    improvement_surcharge: float,
    congestion_surcharge: float,
    airport_fee: float,
) -> float:
    """Sum of all regulatory / situational surcharges.

    Components:
        extra                  â€” rush-hour and overnight extras
        mta_tax                â€” MTA tax ($0.50)
        improvement_surcharge  â€” improvement surcharge ($1.00)
        congestion_surcharge   â€” congestion surcharge ($2.50)
        airport_fee            â€” airport pickup fee ($1.75)
    """
    return extra + mta_tax + improvement_surcharge + congestion_surcharge + airport_fee


def compute_revenue_excl_tolls_surcharges(
    total_amount: float,
    tolls_amount: float,
    surcharges: float,
) -> float:
    """CR-1: Total passenger charge minus tolls and surcharges.

    This isolates the fare + tip components for Finance reporting.
    """
    return total_amount - tolls_amount - surcharges


# Utilisation proxy definition (documented in docs/decisions/)
UTILISATION_PROXY_DESCRIPTION = """
Utilisation proxy = total trip-minutes in a zone-hour / 60.

Interpretation: If a zone-hour has 120 trip-minutes across all pickups that
started in that hour, the utilisation proxy is 2.0 â€” meaning the equivalent
of 2 taxis were actively carrying passengers for the full hour.

This is an approximation. It does NOT account for:
  - Dead-heading (empty return trips)
  - Idle time between fares
  - Fleet size (we don't know how many taxis were available)

It is computed from pickup_datetime and trip_duration_minutes only â€” no
post-trip fields are used as pickup-time demand predictors (NFR-03).
"""
