"""
Central configuration for the AI Predictive Maintenance backend.

Loads environment variables from `.env` file (or host environment variables on Render).
Supports both direct DATABASE_URL (common on Render/Neon/Supabase) and discrete DB_* variables.
"""
import os
from dotenv import load_dotenv

# Load from backend root .env or project root .env
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


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
# Monitored Machines
# ---------------------------------------------------------------------------
_machines_env = os.getenv("MONITORED_MACHINES", "M01,M02,M03")
MACHINES = [m.strip() for m in _machines_env.split(",") if m.strip()]

# ---------------------------------------------------------------------------
# Database Configuration
# ---------------------------------------------------------------------------
# Render and many cloud providers provide DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL")

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

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "").strip()

EMAIL_CONFIG = {
    "resend_api_key": RESEND_API_KEY,
    "brevo_api_key": BREVO_API_KEY,
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

# Cooldown window in minutes between two emails for the same machine
ALERT_COOLDOWN_MINUTES = _get_int("ALERT_COOLDOWN_MINUTES", 15)

# Risk percentage threshold (0-100) to trigger an alert
ALERT_RISK_THRESHOLD = _get_int("ALERT_RISK_THRESHOLD", 60)

# ---------------------------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------------------------
_cors_env = os.getenv("CORS_ORIGINS", "*")
CORS_ORIGINS = [o.strip() for o in _cors_env.split(",") if o.strip()]
if not CORS_ORIGINS:
    CORS_ORIGINS = ["*"]
