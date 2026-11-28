 -- sql/01_dimensions.sql
-- FleetSense Star Schema: Dimension Tables
-- Implements: FR-1.03, FR-1.08 (Shift as calendar dimension column)
  -- 1. dim_zones
-- Taxi zone reference lookup
 CREATE OR REPLACE TABLE dim_zones AS
SELECT
    CAST(LocationID AS INTEGER) AS location_id,
    TRIM(Borough) AS borough,
    TRIM(Zone) AS zone,
    TRIM(service_zone) AS service_zone
FROM read_csv_auto(
    COALESCE(
        TRY_CAST(getvariable('reference_dir') AS VARCHAR),
        'data/reference'
    ) || '/taxi_zone_lookup.csv'
);
 -- 2. dim_calendar
-- Hourly calendar dimension for year 2024 (8,784 hours)
-- Includes shift classification ('Night' vs 'Day') per FR-1.08 / MetroCab spec
 CREATE OR REPLACE TABLE dim_calendar AS
WITH hours_2024 AS (
    SELECT
        dt AS calendar_datetime,
        CAST(dt AS DATE) AS calendar_date,
        EXTRACT(HOUR FROM dt) AS hour_of_day,
        EXTRACT(YEAR FROM dt) AS year,
        EXTRACT(MONTH FROM dt) AS month,
        EXTRACT(DAY FROM dt) AS day,
        DAYOFWEEK(dt) AS day_of_week_iso, -- 1=Monday ... 7=Sunday in DuckDB
        STRFTIME(dt, '%A') AS day_name,
        STRFTIME(dt, '%B') AS month_name
    FROM generate_series(
        TIMESTAMP '2024-01-01 00:00:00',
        TIMESTAMP '2024-12-31 23:00:00',
        INTERVAL 1 HOUR
    ) AS t(dt)
)
SELECT
    calendar_datetime,
    calendar_date,
    hour_of_day,
    year,
    month,
    day,
    day_of_week_iso AS day_of_week,
    day_name,
    month_name,
    -- Weekend flag (Saturday=6, Sunday=7 in ISO)
    CASE WHEN day_of_week_iso IN (6, 7) THEN TRUE ELSE FALSE END AS is_weekend,
    -- Shift classification (FR-1.08: 22:00–05:59 is 'Night', 06:00–21:59 is 'Day')
    CASE
        WHEN hour_of_day >= 22 OR hour_of_day <= 5 THEN 'Night'
        ELSE 'Day'
    END AS shift,
    -- Night shift boolean flag
    CASE
        WHEN hour_of_day >= 22 OR hour_of_day <= 5 THEN TRUE
        ELSE FALSE
    END AS is_night_shift,
    -- US Federal Holidays 2024
    CASE
        WHEN calendar_date = DATE '2024-01-01' THEN 'New Year''s Day'
        WHEN calendar_date = DATE '2024-01-15' THEN 'Martin Luther King Jr. Day'
        WHEN calendar_date = DATE '2024-02-19' THEN 'Washington''s Birthday'
        WHEN calendar_date = DATE '2024-05-27' THEN 'Memorial Day'
        WHEN calendar_date = DATE '2024-06-19' THEN 'Juneteenth National Independence Day'
        WHEN calendar_date = DATE '2024-07-04' THEN 'Independence Day'
        WHEN calendar_date = DATE '2024-09-02' THEN 'Labor Day'
        WHEN calendar_date = DATE '2024-10-14' THEN 'Columbus Day'
        WHEN calendar_date = DATE '2024-11-11' THEN 'Veterans Day'
        WHEN calendar_date = DATE '2024-11-28' THEN 'Thanksgiving Day'
        WHEN calendar_date = DATE '2024-12-25' THEN 'Christmas Day'
        ELSE NULL
    END AS holiday_name,
    CASE
        WHEN calendar_date IN (
            DATE '2024-01-01', DATE '2024-01-15', DATE '2024-02-19',
            DATE '2024-05-27', DATE '2024-06-19', DATE '2024-07-04',
            DATE '2024-09-02', DATE '2024-10-14', DATE '2024-11-11',
            DATE '2024-11-28', DATE '2024-12-25'
        ) THEN TRUE
        ELSE FALSE
    END AS is_holiday
FROM hours_2024;
