-- Cities table
CREATE TABLE IF NOT EXISTS dim_city (
    city_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name         TEXT          NOT NULL,
    country_code CHAR(2)       NOT NULL,
    latitude     NUMERIC(8, 5) NOT NULL CHECK(latitude BETWEEN -90 AND 90),
    longitude    NUMERIC(8, 5) NOT NULL CHECK(longitude BETWEEN -180 AND 180),
    timezone     TEXT          NOT NULL,
    UNIQUE (name, country_code)
);

-- Wheather's table
CREATE TABLE IF NOT EXISTS fact_weather_hourly (
    city_id          INT           NOT NULL REFERENCES dim_city (city_id),
    observed_at      TIMESTAMPTZ   NOT NULL,
    temperature_c    NUMERIC(6, 2) CHECK (temperature_c    BETWEEN -90 AND 60),
    humidity_pct     NUMERIC(6, 2) CHECK (humidity_pct     BETWEEN 0 AND 100),
    precipitation_mm NUMERIC(6, 2) CHECK (precipitation_mm >= 0),
    wind_speed_kmh   NUMERIC(6, 2) CHECK (wind_speed_kmh   >= 0),
    ingested_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    PRIMARY KEY (city_id, observed_at)
);

-- Quarantine: rows that failed on the validation
CREATE TABLE IF NOT EXISTS fact_weather_hourly_quarantine (
    quarantine_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    city_id           INT,
    observed_at       TIMESTAMPTZ,
    temperature_c     NUMERIC,
    humidity_pct      NUMERIC,
    precipitation_mm  NUMERIC,
    wind_speed_kmh    NUMERIC,
    rejection_reason  TEXT NOT NULL,
    run_id            BIGINT REFERENCES etl_run_log (run_id),
    quarantined_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Logs for the pipeline
CREATE TABLE IF NOT EXISTS etl_run_log (
    run_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at    TIMESTAMPTZ,
    status         TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'success', 'failed')),
    rows_extracted INT NOT NULL DEFAULT 0,
    rows_loaded    INT NOT NULL DEFAULT 0,
    error_message  TEXT
);