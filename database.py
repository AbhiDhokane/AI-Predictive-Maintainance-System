"""
PostgreSQL access layer.

Adds an `alert_log` table (on top of the original `sensor_readings` table)
so the system can:
  - remember when the last email alert was sent for each machine
    (used to enforce a cooldown so we don't spam the inbox), and
  - show an "alert history" panel in the dashboard.
"""
import psycopg2
from config import DB_CONFIG


def conn():
    return psycopg2.connect(**DB_CONFIG)


def ensure_schema():
    """Create tables/indexes if they don't already exist. Safe to call every run."""
    x = conn()
    q = x.cursor()
    q.execute("""
        CREATE TABLE IF NOT EXISTS sensor_readings(
            id SERIAL PRIMARY KEY,
            machine_id VARCHAR(20) NOT NULL,
            temperature DOUBLE PRECISION NOT NULL,
            vibration DOUBLE PRECISION NOT NULL,
            current DOUBLE PRECISION NOT NULL,
            rpm INTEGER NOT NULL,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    q.execute("""
        CREATE INDEX IF NOT EXISTS idx_machine_time
        ON sensor_readings(machine_id, recorded_at DESC)
    """)
    q.execute("""
        CREATE TABLE IF NOT EXISTS alert_log(
            id SERIAL PRIMARY KEY,
            machine_id VARCHAR(20) NOT NULL,
            risk_percent DOUBLE PRECISION NOT NULL,
            status VARCHAR(20) NOT NULL,
            recipients TEXT NOT NULL,
            email_status VARCHAR(20) NOT NULL,
            error_message TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    x.commit()
    q.close()
    x.close()


def insert_reading(mid, t, v, c, r):
    x = conn()
    q = x.cursor()
    q.execute(
        "INSERT INTO sensor_readings(machine_id,temperature,vibration,current,rpm) "
        "VALUES(%s,%s,%s,%s,%s)",
        (mid, t, v, c, r),
    )
    x.commit()
    q.close()
    x.close()


def latest():
    x = conn()
    q = x.cursor()
    q.execute(
        "SELECT DISTINCT ON(machine_id) machine_id,temperature,vibration,current,rpm,recorded_at "
        "FROM sensor_readings ORDER BY machine_id,recorded_at DESC"
    )
    a = q.fetchall()
    q.close()
    x.close()
    return a


def history(mid, limit=100):
    x = conn()
    q = x.cursor()
    q.execute(
        "SELECT temperature,vibration,current,rpm,recorded_at FROM sensor_readings "
        "WHERE machine_id=%s ORDER BY recorded_at DESC LIMIT %s",
        (mid, limit),
    )
    a = q.fetchall()
    q.close()
    x.close()
    return a


# ---------------------------------------------------------------------------
# Alert log helpers
# ---------------------------------------------------------------------------
def last_alert_time(mid):
    """Return the timestamp of the most recent alert sent for this machine, or None."""
    x = conn()
    q = x.cursor()
    q.execute(
        "SELECT sent_at FROM alert_log WHERE machine_id=%s ORDER BY sent_at DESC LIMIT 1",
        (mid,),
    )
    row = q.fetchone()
    q.close()
    x.close()
    return row[0] if row else None


def log_alert(mid, risk_percent, status, recipients, email_status, error_message=None):
    x = conn()
    q = x.cursor()
    q.execute(
        "INSERT INTO alert_log(machine_id,risk_percent,status,recipients,email_status,error_message) "
        "VALUES(%s,%s,%s,%s,%s,%s)",
        (mid, risk_percent, status, ",".join(recipients), email_status, error_message),
    )
    x.commit()
    q.close()
    x.close()


def recent_alerts(limit=20):
    x = conn()
    q = x.cursor()
    q.execute(
        "SELECT machine_id,risk_percent,status,recipients,email_status,error_message,sent_at "
        "FROM alert_log ORDER BY sent_at DESC LIMIT %s",
        (limit,),
    )
    a = q.fetchall()
    q.close()
    x.close()
    return a
