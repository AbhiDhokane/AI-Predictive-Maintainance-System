CREATE DATABASE maintenance;
-- Connect to the "maintenance" database, then run everything below:

CREATE TABLE IF NOT EXISTS sensor_readings(
    id SERIAL PRIMARY KEY,
    machine_id VARCHAR(20) NOT NULL,
    temperature DOUBLE PRECISION NOT NULL,
    vibration DOUBLE PRECISION NOT NULL,
    current DOUBLE PRECISION NOT NULL,
    rpm INTEGER NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_machine_time ON sensor_readings(machine_id, recorded_at DESC);

-- New: keeps a record of every email alert attempt (sent or failed),
-- and lets the app enforce a per-machine cooldown between emails.
CREATE TABLE IF NOT EXISTS alert_log(
    id SERIAL PRIMARY KEY,
    machine_id VARCHAR(20) NOT NULL,
    risk_percent DOUBLE PRECISION NOT NULL,
    status VARCHAR(20) NOT NULL,
    recipients TEXT NOT NULL,
    email_status VARCHAR(20) NOT NULL,
    error_message TEXT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Note: app.py / sensor_simulator.py also call ensure_schema() automatically
-- on startup, so running this script by hand is optional but recommended.
