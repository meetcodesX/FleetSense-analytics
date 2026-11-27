"""Unit tests for FleetSense canonical metrics (FR-1.04, CR-1)."""

from __future__ import annotations

from fleetsense.metrics import (
    compute_revenue_excl_tolls_surcharges,
    compute_surcharges,
)


def test_compute_surcharges():
    """Verify sum of surcharges across all 5 standard TLC fee components."""
    extra = 1.0
    mta_tax = 0.5
    improvement = 1.0
    congestion = 2.5
    airport = 1.75

    total_surcharges = compute_surcharges(extra, mta_tax, improvement, congestion, airport)
    assert total_surcharges == 6.75


def test_compute_revenue_excl_tolls_surcharges():
    """Verify CR-1: revenue excluding tolls and surcharges isolates fare + tips."""
    total_amount = 35.0
    tolls_amount = 6.55
    surcharges = 4.0  # extra + mta_tax + improvement + congestion

    excl = compute_revenue_excl_tolls_surcharges(total_amount, tolls_amount, surcharges)
    # 35.0 - 6.55 - 4.0 = 24.45 (which equals fare + tip)
    assert round(excl, 2) == 24.45


def test_zero_tolls_surcharges():
    """Verify when tolls and surcharges are 0, excl revenue equals total_amount."""
    total_amount = 20.0
    excl = compute_revenue_excl_tolls_surcharges(total_amount, 0.0, 0.0)
    assert excl == 20.0
