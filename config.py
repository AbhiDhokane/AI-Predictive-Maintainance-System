"""
Central configuration for the AI Predictive Maintenance system.

All secrets/settings are loaded from environment variables (via a local
.env file) instead of being hard-coded, so credentials never end up in
source control. Copy .env.example to .env and fill in your real values.
"""
import os
from dotenv import load_dotenv

load_dotenv()  # reads the .env file in the project root, if present


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    try:
        return int(val) if val is not None else default
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Machines being monitored
# ---------------------------------------------------------------------------
MACHINES = ["M01", "M02", "M03"]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": _get_int("DB_PORT", 5432),
    "database": os.getenv("DB_NAME", "maintenance"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

# ---------------------------------------------------------------------------
# Email alerts
# ---------------------------------------------------------------------------
EMAIL_ALERTS_ENABLED = _get_bool("EMAIL_ALERTS_ENABLED", True)

EMAIL_CONFIG = {
    "smtp_host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
    "smtp_port": _get_int("SMTP_PORT", 587),
    "smtp_user": os.getenv("SMTP_USER", ""),
    "smtp_password": os.getenv("SMTP_PASSWORD", ""),
    "email_from": os.getenv("EMAIL_FROM", os.getenv("SMTP_USER", "")),
    "recipients": [
        r.strip()
        for r in os.getenv("ALERT_RECIPIENTS", "").split(",")
        if r.strip()
    ],
}

# Only re-alert on the same machine after this many minutes have passed
ALERT_COOLDOWN_MINUTES = _get_int("ALERT_COOLDOWN_MINUTES", 15)

# Risk percentage (0-100) at/above which a "HIGH FAILURE RISK" email fires
ALERT_RISK_THRESHOLD = _get_int("ALERT_RISK_THRESHOLD", 60)
