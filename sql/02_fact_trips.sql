 -- sql/02_fact_trips.sql
-- FleetSense Star Schema: Fact Table
-- Implements: FR-1.03, FR-1.04, CR-1, FR-1.08
 CREATE OR REPLACE TABLE fact_trips AS
SELECT
    -- Vendor and trip timestamps
    CAST(VendorID AS INTEGER) AS vendor_id,
    tpep_pickup_datetime AS pickup_datetime,
    tpep_dropoff_datetime AS dropoff_datetime,
    
    -- Location foreign keys
    CAST(PULocationID AS INTEGER) AS pickup_location_id,
    CAST(DOLocationID AS INTEGER) AS dropoff_location_id,
    
    -- Trip characteristics
    COALESCE(CAST(passenger_count AS INTEGER), 0) AS passenger_count,
    CAST(trip_distance AS DOUBLE) AS trip_distance,
    CAST(RatecodeID AS INTEGER) AS rate_code_id,
    store_and_fwd_flag,
    CAST(payment_type AS INTEGER) AS payment_type,
    
    -- Trip duration in minutes
    ROUND(
        EXTRACT(EPOCH FROM (tpep_dropoff_datetime - tpep_pickup_datetime)) / 60.0,
        2
    ) AS trip_duration_minutes,
    
    -- Calendar & Shift attributes (FR-1.08: classify calendar date & shift by pickup time)
    CAST(tpep_pickup_datetime AS DATE) AS pickup_date,
    EXTRACT(HOUR FROM tpep_pickup_datetime) AS pickup_hour,
    STRFTIME(tpep_pickup_datetime, '%Y-%m') AS pickup_month_year,
    
    -- Shift (Night: 22:00–05:59, Day: 06:00–21:59)
    CASE
        WHEN EXTRACT(HOUR FROM tpep_pickup_datetime) >= 22
          OR EXTRACT(HOUR FROM tpep_pickup_datetime) <= 5
        THEN 'Night'
        ELSE 'Day'
    END AS shift,
    
    CASE
        WHEN EXTRACT(HOUR FROM tpep_pickup_datetime) >= 22
          OR EXTRACT(HOUR FROM tpep_pickup_datetime) <= 5
        THEN TRUE
        ELSE FALSE
    END AS is_night_shift,
    
    -- Revenue component breakdown (FR-1.04)
    CAST(fare_amount AS DOUBLE) AS fare_amount,
    CAST(fare_amount AS DOUBLE) AS fare_revenue,
    CAST(tip_amount AS DOUBLE) AS tip_amount,
    CAST(tip_amount AS DOUBLE) AS tip_revenue,
    CAST(tolls_amount AS DOUBLE) AS tolls_amount,
    CAST(tolls_amount AS DOUBLE) AS tolls_revenue,
    CAST(total_amount AS DOUBLE) AS total_amount,
    CAST(total_amount AS DOUBLE) AS total_revenue,
    
    -- Surcharges sum (extra + mta_tax + improvement_surcharge + congestion_surcharge + airport_fee)
    ROUND(
        CAST(COALESCE(extra, 0.0) AS DOUBLE) +
        CAST(COALESCE(mta_tax, 0.0) AS DOUBLE) +
        CAST(COALESCE(improvement_surcharge, 0.0) AS DOUBLE) +
        CAST(COALESCE(congestion_surcharge, 0.0) AS DOUBLE) +
        CAST(COALESCE(airport_fee, 0.0) AS DOUBLE),
        2
    ) AS surcharges_revenue,
    
    -- Base surcharge columns preserved
    CAST(extra AS DOUBLE) AS extra,
    CAST(mta_tax AS DOUBLE) AS mta_tax,
    CAST(improvement_surcharge AS DOUBLE) AS improvement_surcharge,
    CAST(congestion_surcharge AS DOUBLE) AS congestion_surcharge,
    CAST(airport_fee AS DOUBLE) AS airport_fee,
    
    
    -- CR-1: Revenue excluding tolls and surcharges (fare + tip only)
    ROUND(
        CAST(total_amount AS DOUBLE) -
        CAST(COALESCE(tolls_amount, 0.0) AS DOUBLE) -
        (
            CAST(COALESCE(extra, 0.0) AS DOUBLE) +
            CAST(COALESCE(mta_tax, 0.0) AS DOUBLE) +
            CAST(COALESCE(improvement_surcharge, 0.0) AS DOUBLE) +
            CAST(COALESCE(congestion_surcharge, 0.0) AS DOUBLE) +
            CAST(COALESCE(airport_fee, 0.0) AS DOUBLE)
        ),
        2
    ) AS revenue_excl_tolls_surcharges

FROM read_parquet(
    COALESCE(
        TRY_CAST(getvariable('validated_dir') AS VARCHAR),
        'data/validated'
    ) || '/*.parquet'
);
