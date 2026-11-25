"""FleetSense configuration â€” paths, constants, and validation thresholds.

Single source of truth for all configurable values. Never hardcode paths
or thresholds elsewhere; import from here.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DATA_DIR = Path(os.getenv("FLEETSENSE_DATA_DIR", PROJECT_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
QUARANTINE_DIR = DATA_DIR / "quarantine"
WAREHOUSE_DIR = DATA_DIR / "warehouse"
REFERENCE_DIR = DATA_DIR / "reference"
QUALITY_REPORTS_DIR = DATA_DIR / "quality_reports"
MARTS_DIR = DATA_DIR / "marts"
SQL_DIR = PROJECT_ROOT / "sql"

DUCKDB_PATH = WAREHOUSE_DIR / "fleetsense.duckdb"
# Data source URLs
TLC_BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"
ZONE_LOOKUP_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
# Dataset scope
DATA_YEAR: int = int(os.getenv("FLEETSENSE_DATA_YEAR", "2024"))
DATA_MONTHS: list[int] = list(range(1, 13))
# Validation thresholds  (FR-1.02 / AC-1.2)
DATA_START_DATE = f"{DATA_YEAR}-01-01"
DATA_END_DATE = f"{DATA_YEAR + 1}-01-01"

MIN_TRIP_DURATION_MINUTES: float = 1.0
MAX_TRIP_DURATION_MINUTES: float = 240.0
FLAG_LONG_TRIP_MINUTES: float = 60.0  # Flag in quality report, do NOT quarantine

MAX_PASSENGER_COUNT: int = 9  # Quarantine if > 9; keep 0/NULL as "unknown"
MAX_TRIP_DISTANCE_MILES: float = 200.0
MAX_FARE_AMOUNT: float = 500.0
MAX_TOTAL_AMOUNT: float = 1000.0

MIN_LOCATION_ID: int = 1
MAX_LOCATION_ID: int = 263
# Night-shift definition  (22:00â€“05:59, by pickup hour)
NIGHT_SHIFT_START_HOUR: int = 22  # inclusive
NIGHT_SHIFT_END_HOUR: int = 5  # inclusive (wraps past midnight)
# Pipeline output
RUN_LOG_PATH = QUALITY_REPORTS_DIR / "run_log.jsonl"
QUALITY_SUMMARY_PATH = QUALITY_REPORTS_DIR / "quality_summary.json"
# Logging
LOG_LEVEL: str = os.getenv("FLEETSENSE_LOG_LEVEL", "INFO")
