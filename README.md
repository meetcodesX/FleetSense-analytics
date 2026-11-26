# FleetSense — NYC Taxi Operations & Analytics Platform (2024)

**Live Operations Dashboard:** `[PASTE-YOUR-STREAMLIT-URL-HERE]` *(Deploy `app/dashboard.py` via Streamlit Community Cloud)*  
**Repository:** `https://github.com/meetcodesX/fleetsense`  
**Release:** `v1.0.0` (Phase 1 — Data Engineering, Analytical Warehouse & Operations BI)

FleetSense is an end-to-end, reproducible analytics pipeline and interactive operations dashboard built on **41.17 million** 2024 NYC TLC Yellow Taxi trip records. Designed for **MetroCab Operations** and **Halvorsen Dusk Rides**, it enforces automated data quality quarantine rules, separates pass-through tolls and surcharges from clean operating revenue (**CR-1**), models Day vs. Night shift dynamics (**FR-1.08**), and serves pre-aggregated Parquet marts for sub-2-second dashboard responsiveness (**NFR-05**).

---

## Key 2024 Pipeline & Analytical Highlights

| Metric / Benchmark | Verified 2024 Result | Requirement |
| :--- | :--- | :--- |
| **Raw Records Ingested** | `41,169,720` rows (12 monthly Parquet files) | `FR-1.01` / `AC-1.1` |
| **Clean Trips Loaded** | `39,192,169` trips (`95.20%` pass rate) | `FR-1.02` / `AC-1.2` |
| **Quarantined Records** | `1,977,551` rows (`4.80%`, 100% reconciled) | `FR-1.02` / `AC-1.2` |
| **Full 12-Month Pipeline Runtime** | `79.3 seconds` (~1.3 min; target `< 15 min`) | `NFR-05` |
| **Exported Mart Footprint** | `7.95 MB` across 7 Parquet marts | `NFR-05` |
| **Dashboard Filter Latency** | `< 2.0 seconds` (cached Parquet marts) | `FR-1.06` / `NFR-05` |
| **Operating Shift Split (`FR-1.08`)** | Day (`06:00–21:59`): `82.5%` trips (`32.33M`) \| Night (`22:00–05:59`): `17.5%` trips (`6.86M`) | `FR-1.08` / `AC-1.5` |

---

## Architecture Overview

```text
NYC TLC CloudFront (2024-01 .. 2024-12 Parquet + Taxi Zone Lookup CSV)
        │
        ▼  [1. Idempotent Ingestion]  src/fleetsense/ingest.py
  data/raw/  (cached locally; skips re-download on repeat runs)
        │
        ▼  [2. Quality & Quarantine]  src/fleetsense/validate.py
  data/validated/  +  data/quarantine/  +  data/quality_reports/run_log.jsonl
        │  (Enforces: rows_in == rows_loaded + rows_quarantined)
        ▼  [3. DuckDB Star Schema]   src/fleetsense/warehouse.py & sql/
  data/warehouse/fleetsense.duckdb
  ├── dim_zones (265 NYC TLC zones & boroughs)
  ├── dim_calendar (8,784 hourly slots with Day/Night shift classification)
  ├── fact_trips (39,192,169 validated trips with CR-1 revenue columns)
  └── hourly_zone_demand (2,327,760 zone-hour demand & utilisation records)
        │
        ▼  [4. Analytical Marts]      data/marts/*.parquet (7.95 MB total)
        ▼  [5. Streamlit Ops UI]      app/dashboard.py (< 2s interactive queries)
```

---

## First-Time User & Dashboard Guide (`D-1.2`)

1. **Open the Dashboard:** Visit the live Streamlit URL above (or run locally via `uv run streamlit run app/dashboard.py`).
2. **Filter Scope (Left Sidebar):**
   * **Calendar Month Range:** Slide between `Month 01` and `Month 12` to isolate seasonal periods.
   * **Operating Shift (`FR-1.08`):** Toggle between **All Shifts**, **Day Shift (`06:00–21:59`)**, and **Night Shift (`22:00–05:59`)** for Halvorsen Dusk Rides shift analysis.
   * **Borough & Specific Taxi Zones:** Filter down to one or more NYC boroughs or individual zones (e.g., `JFK Airport`, `Midtown Center`, `Bayside`).
3. **Explore the 4 Operational Tabs:**
   * **Executive Overview:** Dynamic KPI cards (Total Trips, Passenger Charges, Average Fare, Average Duration, Utilisation Proxy), Day vs. Night shift comparison, and monthly/daily demand trajectories.
   * **Demand & Zone Intelligence:** Top/bottom taxi zones by volume, a 7-day × 24-hour demand heatmap, and Day vs. Night zone divergence rankings.
   * **Finance Revenue Breakdown (`CR-1` / `AC-1.4`):** Separates **Clean Revenue (`Fare + Tips`)** from pass-through **Tolls & Surcharges** across high-toll airport and bridge corridors.
   * **Data Quality & Reconciliation (`AC-1.2`):** Full monthly audit table proving `rows_in == rows_loaded + rows_quarantined` and documenting edge-case rules.

---

## Local Setup & One-Command Clean Rebuild (`NFR-01`)

### Prerequisites
* Python **3.11+** (tested on Python 3.13)
* [`uv`](https://docs.astral.sh/uv/) package manager

### 1. Clone & Install Dependencies
```bash
git clone [https://github.com/meetcodesX/fleetsense.git](https://github.com/meetcodesX/fleetsense.git)
cd fleetsense
uv sync
```

### 2. Run the Complete End-to-End Pipeline (`all`)
Downloads all 12 months of 2024 TLC Yellow Taxi data idempotently, validates and quarantines invalid rows, builds the DuckDB warehouse, and exports the Parquet marts:
```bash
uv run python -m fleetsense.cli all
```
*(Or via Make on Linux/macOS/Git Bash: `make all`)*

### 3. Launch the Operations Dashboard Locally
```bash
uv run streamlit run app/dashboard.py
```
The dashboard will open at `http://localhost:8501`.

### 4. Individual CLI Commands
```bash
uv run python -m fleetsense.cli ingest              # Download & verify raw 2024 Parquet files (idempotent)
uv run python -m fleetsense.cli validate            # Validate rows, write quarantine files & reconciliation log
uv run python -m fleetsense.cli build-warehouse     # Build DuckDB star schema & export compact marts
uv run python -m fleetsense.cli add-month --year 2024 --month 12  # Incrementally ingest a single month
```

---

## Testing & Code Quality (`NFR-06`)

Run the linter, formatter check, and automated unit/integration test suite:
```bash
uv run ruff check src/ tests/ app/
uv run pytest -v
```

---

## Repository Structure

```text
FleetSense/
├── app/
│   └── dashboard.py              # Multi-tab Streamlit operations dashboard (FR-1.06)
├── data/
│   ├── marts/                    # Pre-aggregated Parquet marts tracked for fast deployment (7.95 MB)
│   ├── quality_reports/          # Reconciliation logs (run_log.jsonl) & ingestion metadata
│   └── reference/                # Official NYC TLC taxi_zone_lookup.csv
├── docs/
│   ├── findings_report.md        # Non-technical operational findings & Halvorsen shift report (D-1.6)
│   ├── technical_design.md       # Architecture, star schema & performance design (D-1.3)
│   ├── data_dictionary.md        # Warehouse & mart column definitions (NFR-09)
│   ├── runbook.md                # Operational rebuild, monthly ingestion & rollback guide (D-1.8)
│   ├── decisions/                # Architecture Decision Records (ADRs)
│   └── retros/                   # Project retrospective
├── notebooks/                    # Exploratory data analysis & baseline comparisons
├── sql/
│   ├── 01_dimensions.sql         # dim_zones & dim_calendar (with Day/Night shift mapping)
│   ├── 02_fact_trips.sql         # fact_trips with CR-1 surcharges & clean revenue derivations
│   └── 03_marts.sql              # Aggregated marts & hourly_zone_demand tables
├── src/fleetsense/
│   ├── cli.py                    # Click CLI entrypoints (ingest, validate, build-warehouse, add-month, all)
│   ├── client_analysis.py        # Halvorsen Dusk Rides shift-split analytics (FR-1.08)
│   ├── config.py                 # Central paths, thresholds & 2024 TLC URLs
│   ├── eda.py                    # 12-month seasonality, anomaly & naive baseline analysis (NFR-04)
│   ├── ingest.py                 # Idempotent CloudFront downloader & Parquet schema verifier
│   ├── metrics.py                # CR-1 revenue & surcharge calculation helpers
│   ├── validate.py               # Quarantine rules engine & JSONL reconciliation logger
│   └── warehouse.py              # DuckDB builder & Parquet mart exporter
├── tests/                        # Unit & end-to-end warehouse integration tests
├── CHANGELOG.md                  # v1.0.0 release notes & benchmark summary (D-1.7)
├── Dockerfile                    # Containerized runtime environment
├── Makefile                      # Standard automation targets
└── pyproject.toml                # Project dependencies & Ruff/Pytest configuration
```

---

## Governance & Data Quality Rules Summary

* **Revenue Governance (`CR-1`):** Gross passenger charges (`total_amount`) include pass-through tolls, MTA tax, improvement surcharges, congestion surcharges, and airport fees. Clean operating revenue is strictly defined as `fare_amount + tip_amount`.
* **Shift Definition (`FR-1.08`):** Trips are classified by pickup timestamp into **Night Shift (`22:00–05:59`)** and **Day Shift (`06:00–21:59`)**, preserving midnight-crossing trips accurately.
* **Quarantine Policy (`FR-1.02`):** Trips with duration `< 1 min` or `> 240 min`, distance `<= 0` or `> 200 mi`, invalid fare/total amounts, out-of-2024 timestamps, or exact duplicate rows are quarantined—while `passenger_count = 0` or `NULL` is retained as `"unknown"` to avoid discarding valid street hails.
