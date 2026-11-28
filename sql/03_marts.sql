 -- sql/03_marts.sql
-- FleetSense Star Schema: Analytical Marts
-- Implements: FR-1.03, FR-1.04, CR-1, FR-1.08
  -- 1. hourly_zone_demand
-- Complete hourly time-series per zone with ZERO-DEMAND hours explicitly filled
-- Includes shift dimension (FR-1.08) and CR-1 revenue breakdown
 CREATE OR REPLACE TABLE hourly_zone_demand AS
WITH active_hours AS (
    SELECT
        c.calendar_datetime,
        c.hour_of_day,
        c.shift,
        c.is_night_shift,
        c.is_weekend
    FROM dim_calendar c
    WHERE c.calendar_datetime >= (SELECT MIN(DATE_TRUNC('hour', pickup_datetime)) FROM fact_trips)
      AND c.calendar_datetime <= (SELECT MAX(DATE_TRUNC('hour', pickup_datetime)) FROM fact_trips)
),
zone_hour_grid AS (
    SELECT
        z.location_id,
        h.calendar_datetime AS hour_start,
        h.hour_of_day,
        h.shift,
        h.is_night_shift,
        h.is_weekend
    FROM dim_zones z
    CROSS JOIN active_hours h
),
actual_demand AS (
    SELECT
        pickup_location_id AS location_id,
        DATE_TRUNC('hour', pickup_datetime) AS hour_start,
        COUNT(*) AS trip_count,
        SUM(total_revenue) AS total_revenue,
        SUM(fare_revenue) AS fare_revenue,
        SUM(tolls_revenue) AS tolls_revenue,
        SUM(surcharges_revenue) AS surcharges_revenue,
        SUM(revenue_excl_tolls_surcharges) AS revenue_excl_tolls_surcharges,
        AVG(fare_revenue) AS avg_fare,
        AVG(trip_duration_minutes) AS avg_duration_minutes,
        SUM(trip_duration_minutes) AS total_trip_minutes
    FROM fact_trips
    GROUP BY 1, 2
)
SELECT
    g.location_id,
    g.hour_start,
    g.hour_of_day,
    g.shift,
    g.is_night_shift,
    g.is_weekend,
    COALESCE(a.trip_count, 0) AS trip_count,
    ROUND(COALESCE(a.total_revenue, 0.0), 2) AS total_revenue,
    ROUND(COALESCE(a.fare_revenue, 0.0), 2) AS fare_revenue,
    ROUND(COALESCE(a.tolls_revenue, 0.0), 2) AS tolls_revenue,
    ROUND(COALESCE(a.surcharges_revenue, 0.0), 2) AS surcharges_revenue,
    ROUND(COALESCE(a.revenue_excl_tolls_surcharges, 0.0), 2) AS revenue_excl_tolls_surcharges,
    ROUND(COALESCE(a.avg_fare, 0.0), 2) AS avg_fare,
    ROUND(COALESCE(a.avg_duration_minutes, 0.0), 2) AS avg_duration_minutes,
    -- Utilisation proxy: total trip duration minutes / 60
    ROUND(COALESCE(a.total_trip_minutes, 0.0) / 60.0, 3) AS utilisation_proxy
FROM zone_hour_grid g
LEFT JOIN actual_demand a
    ON g.location_id = a.location_id
   AND g.hour_start = a.hour_start
ORDER BY g.hour_start, g.location_id;
