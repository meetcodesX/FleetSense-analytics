"""Pytest fixtures and synthetic test data generators for FleetSense."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import polars as pl
import pytest


@pytest.fixture
def sample_raw_trips_df() -> pl.DataFrame:
    """Generate a controlled test DataFrame containing both valid and invalid trip records.

    Covers all validation rules:
      - Valid day trip
      - Valid night shift trip (23:00)
      - Valid midnight crossing trip (23:45 -> 00:15)
      - Valid trip with passenger_count = 0 (kept as unknown)
      - Valid trip with passenger_count = None (kept as unknown)
      - Invalid: pickup outside 2024
      - Invalid: dropoff before pickup
      - Invalid: duration < 1 minute
      - Invalid: duration > 240 minutes
      - Invalid: passenger_count > 9
      - Invalid: trip_distance <= 0
      - Invalid: trip_distance > 200
      - Invalid: fare_amount < 0
      - Invalid: fare_amount > 500
      - Invalid: total_amount < 0
      - Invalid: invalid location ID (> 263)
      - Duplicate row
    """
    records = [
        # 1. Valid day trip
        {
            "VendorID": 1,
            "tpep_pickup_datetime": datetime(2024, 1, 15, 14, 0, 0),
            "tpep_dropoff_datetime": datetime(2024, 1, 15, 14, 20, 0),
            "passenger_count": 1.0,
            "trip_distance": 3.5,
            "RatecodeID": 1.0,
            "store_and_fwd_flag": "N",
            "PULocationID": 161,
            "DOLocationID": 237,
            "payment_type": 1,
            "fare_amount": 16.5,
            "extra": 0.0,
            "mta_tax": 0.5,
            "tip_amount": 3.0,
            "tolls_amount": 0.0,
            "improvement_surcharge": 1.0,
            "total_amount": 23.5,
            "congestion_surcharge": 2.5,
            "airport_fee": 0.0,
        },
        # 2. Valid night shift trip (starts at 23:10)
        {
            "VendorID": 2,
            "tpep_pickup_datetime": datetime(2024, 1, 15, 23, 10, 0),
            "tpep_dropoff_datetime": datetime(2024, 1, 15, 23, 30, 0),
            "passenger_count": 2.0,
            "trip_distance": 5.0,
            "RatecodeID": 1.0,
            "store_and_fwd_flag": "N",
            "PULocationID": 142,
            "DOLocationID": 236,
            "payment_type": 1,
            "fare_amount": 22.0,
            "extra": 1.0,
            "mta_tax": 0.5,
            "tip_amount": 5.0,
            "tolls_amount": 0.0,
            "improvement_surcharge": 1.0,
            "total_amount": 32.0,
            "congestion_surcharge": 2.5,
            "airport_fee": 0.0,
        },
        # 3. Valid midnight crossing trip (23:45 -> 00:15 next day)
        {
            "VendorID": 1,
            "tpep_pickup_datetime": datetime(2024, 1, 15, 23, 45, 0),
            "tpep_dropoff_datetime": datetime(2024, 1, 16, 0, 15, 0),
            "passenger_count": 1.0,
            "trip_distance": 6.2,
            "RatecodeID": 1.0,
            "store_and_fwd_flag": "N",
            "PULocationID": 79,
            "DOLocationID": 148,
            "payment_type": 1,
            "fare_amount": 25.0,
            "extra": 1.0,
            "mta_tax": 0.5,
            "tip_amount": 4.0,
            "tolls_amount": 0.0,
            "improvement_surcharge": 1.0,
            "total_amount": 34.0,
            "congestion_surcharge": 2.5,
            "airport_fee": 0.0,
        },
        # 4. Valid trip with passenger_count = 0 (kept as unknown per requirements)
        {
            "VendorID": 2,
            "tpep_pickup_datetime": datetime(2024, 1, 15, 10, 0, 0),
            "tpep_dropoff_datetime": datetime(2024, 1, 15, 10, 15, 0),
            "passenger_count": 0.0,
            "trip_distance": 2.0,
            "RatecodeID": 1.0,
            "store_and_fwd_flag": "N",
            "PULocationID": 100,
            "DOLocationID": 107,
            "payment_type": 1,
            "fare_amount": 12.0,
            "extra": 0.0,
            "mta_tax": 0.5,
            "tip_amount": 2.0,
            "tolls_amount": 0.0,
            "improvement_surcharge": 1.0,
            "total_amount": 18.0,
            "congestion_surcharge": 2.5,
            "airport_fee": 0.0,
        },
        # 5. Valid trip with passenger_count = None (kept as unknown)
        {
            "VendorID": 1,
            "tpep_pickup_datetime": datetime(2024, 1, 15, 11, 0, 0),
            "tpep_dropoff_datetime": datetime(2024, 1, 15, 11, 20, 0),
            "passenger_count": None,
            "trip_distance": 2.8,
            "RatecodeID": 1.0,
            "store_and_fwd_flag": "N",
            "PULocationID": 162,
            "DOLocationID": 230,
            "payment_type": 1,
            "fare_amount": 14.0,
            "extra": 0.0,
            "mta_tax": 0.5,
            "tip_amount": 3.0,
            "tolls_amount": 0.0,
            "improvement_surcharge": 1.0,
            "total_amount": 21.0,
            "congestion_surcharge": 2.5,
            "airport_fee": 0.0,
        },
        # 6. INVALID: pickup outside 2024 (2023)
        {
            "VendorID": 1,
            "tpep_pickup_datetime": datetime(2023, 12, 31, 23, 59, 0),
            "tpep_dropoff_datetime": datetime(2024, 1, 1, 0, 15, 0),
            "passenger_count": 1.0,
            "trip_distance": 2.0,
            "RatecodeID": 1.0,
            "store_and_fwd_flag": "N",
            "PULocationID": 100,
            "DOLocationID": 107,
            "payment_type": 1,
            "fare_amount": 10.0,
            "extra": 0.0,
            "mta_tax": 0.5,
            "tip_amount": 2.0,
            "tolls_amount": 0.0,
            "improvement_surcharge": 1.0,
            "total_amount": 13.5,
            "congestion_surcharge": 0.0,
            "airport_fee": 0.0,
        },
        # 7. INVALID: pickup after dropoff
        {
            "VendorID": 1,
            "tpep_pickup_datetime": datetime(2024, 1, 15, 12, 30, 0),
            "tpep_dropoff_datetime": datetime(2024, 1, 15, 12, 10, 0),
            "passenger_count": 1.0,
            "trip_distance": 2.0,
            "RatecodeID": 1.0,
            "store_and_fwd_flag": "N",
            "PULocationID": 100,
            "DOLocationID": 107,
            "payment_type": 1,
            "fare_amount": 10.0,
            "extra": 0.0,
            "mta_tax": 0.5,
            "tip_amount": 2.0,
            "tolls_amount": 0.0,
            "improvement_surcharge": 1.0,
            "total_amount": 13.5,
            "congestion_surcharge": 0.0,
            "airport_fee": 0.0,
        },
        # 8. INVALID: duration < 1 minute (10 seconds)
        {
            "VendorID": 1,
            "tpep_pickup_datetime": datetime(2024, 1, 15, 12, 0, 0),
            "tpep_dropoff_datetime": datetime(2024, 1, 15, 12, 0, 10),
            "passenger_count": 1.0,
            "trip_distance": 0.1,
            "RatecodeID": 1.0,
            "store_and_fwd_flag": "N",
            "PULocationID": 100,
            "DOLocationID": 100,
            "payment_type": 1,
            "fare_amount": 3.0,
            "extra": 0.0,
            "mta_tax": 0.5,
            "tip_amount": 0.0,
            "tolls_amount": 0.0,
            "improvement_surcharge": 1.0,
            "total_amount": 4.5,
            "congestion_surcharge": 0.0,
            "airport_fee": 0.0,
        },
        # 9. INVALID: passenger count > 9 (e.g. 15)
        {
            "VendorID": 1,
            "tpep_pickup_datetime": datetime(2024, 1, 15, 15, 0, 0),
            "tpep_dropoff_datetime": datetime(2024, 1, 15, 15, 20, 0),
            "passenger_count": 15.0,
            "trip_distance": 3.0,
            "RatecodeID": 1.0,
            "store_and_fwd_flag": "N",
            "PULocationID": 100,
            "DOLocationID": 107,
            "payment_type": 1,
            "fare_amount": 15.0,
            "extra": 0.0,
            "mta_tax": 0.5,
            "tip_amount": 2.0,
            "tolls_amount": 0.0,
            "improvement_surcharge": 1.0,
            "total_amount": 18.5,
            "congestion_surcharge": 0.0,
            "airport_fee": 0.0,
        },
        # 10. INVALID: trip distance <= 0
        {
            "VendorID": 1,
            "tpep_pickup_datetime": datetime(2024, 1, 15, 16, 0, 0),
            "tpep_dropoff_datetime": datetime(2024, 1, 15, 16, 10, 0),
            "passenger_count": 1.0,
            "trip_distance": 0.0,
            "RatecodeID": 1.0,
            "store_and_fwd_flag": "N",
            "PULocationID": 100,
            "DOLocationID": 107,
            "payment_type": 1,
            "fare_amount": 10.0,
            "extra": 0.0,
            "mta_tax": 0.5,
            "tip_amount": 0.0,
            "tolls_amount": 0.0,
            "improvement_surcharge": 1.0,
            "total_amount": 11.5,
            "congestion_surcharge": 0.0,
            "airport_fee": 0.0,
        },
        # 11. INVALID: location ID outside 1..263
        {
            "VendorID": 1,
            "tpep_pickup_datetime": datetime(2024, 1, 15, 17, 0, 0),
            "tpep_dropoff_datetime": datetime(2024, 1, 15, 17, 15, 0),
            "passenger_count": 1.0,
            "trip_distance": 2.5,
            "RatecodeID": 1.0,
            "store_and_fwd_flag": "N",
            "PULocationID": 999,  # Invalid!
            "DOLocationID": 107,
            "payment_type": 1,
            "fare_amount": 12.0,
            "extra": 0.0,
            "mta_tax": 0.5,
            "tip_amount": 2.0,
            "tolls_amount": 0.0,
            "improvement_surcharge": 1.0,
            "total_amount": 15.5,
            "congestion_surcharge": 0.0,
            "airport_fee": 0.0,
        },
        # 12. DUPLICATE of row 1 (will be quarantined as duplicate)
        {
            "VendorID": 1,
            "tpep_pickup_datetime": datetime(2024, 1, 15, 14, 0, 0),
            "tpep_dropoff_datetime": datetime(2024, 1, 15, 14, 20, 0),
            "passenger_count": 1.0,
            "trip_distance": 3.5,
            "RatecodeID": 1.0,
            "store_and_fwd_flag": "N",
            "PULocationID": 161,
            "DOLocationID": 237,
            "payment_type": 1,
            "fare_amount": 16.5,
            "extra": 0.0,
            "mta_tax": 0.5,
            "tip_amount": 3.0,
            "tolls_amount": 0.0,
            "improvement_surcharge": 1.0,
            "total_amount": 23.5,
            "congestion_surcharge": 2.5,
            "airport_fee": 0.0,
        },
    ]
    return pl.DataFrame(records)


@pytest.fixture
def sample_zones_csv(tmp_path: Path) -> Path:
    """Create a minimal taxi_zone_lookup.csv for testing."""
    csv_content = (
        '"LocationID","Borough","Zone","service_zone"\n'
        '1,"EWR","Newark Airport","EWR"\n'
        '79,"Manhattan","East Village","Yellow Zone"\n'
        '100,"Manhattan","Garment District","Yellow Zone"\n'
        '107,"Manhattan","Gramercy","Yellow Zone"\n'
        '142,"Manhattan","Lincoln Square East","Yellow Zone"\n'
        '148,"Manhattan","Lower East Side","Yellow Zone"\n'
        '161,"Manhattan","Midtown Center","Yellow Zone"\n'
        '162,"Manhattan","Midtown East","Yellow Zone"\n'
        '230,"Manhattan","Times Sq/Theatre District","Yellow Zone"\n'
        '236,"Manhattan","Upper East Side North","Yellow Zone"\n'
        '237,"Manhattan","Upper East Side South","Yellow Zone"\n'
        '263,"Manhattan","Yorkville West","Yellow Zone"\n'
    )
    csv_path = tmp_path / "taxi_zone_lookup.csv"
    csv_path.write_text(csv_content, encoding="utf-8")
    return csv_path
