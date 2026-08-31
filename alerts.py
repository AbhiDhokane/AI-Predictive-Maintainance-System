"""
Real email alerting for the predictive maintenance system.

When a machine's AI-predicted failure risk crosses the configured
threshold, `maybe_send_alert()` sends an actual SMTP email to the
configured recipients (e.g. via Gmail) and records the attempt in the
`alert_log` table. A cooldown window prevents the same machine from
spamming the inbox every few seconds while it stays in a bad state.
"""
import smtplib
import ssl
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import EMAIL_CONFIG, EMAIL_ALERTS_ENABLED, ALERT_COOLDOWN_MINUTES
from database import last_alert_time, log_alert


def _build_email(machine_id, status, risk_percent, sensor):
    cfg = EMAIL_CONFIG
    subject = f"[Predictive Maintenance] {machine_id} - {status} ({risk_percent:.1f}% risk)"

    body = f"""\
Automated alert from the AI Predictive Maintenance System

Machine:        {machine_id}
Status:         {status}
Failure risk:   {risk_percent:.1f}%
Detected at:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Latest sensor readings
-----------------------
Temperature:  {sensor['temperature']:.1f} \u00b0C
Vibration:    {sensor['vibration']:.2f} mm/s
Current:      {sensor['current']:.2f} A
RPM:          {sensor['rpm']:.0f}

Recommended action: schedule an inspection / maintenance for this
machine as soon as possible.

This is an automated message - please do not reply.
"""

    msg = MIMEMultipart()
    msg["From"] = cfg["email_from"]
    msg["To"] = ", ".join(cfg["recipients"])
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    return msg


def _send_smtp(msg):
    """Actually send the email over SMTP with STARTTLS. Raises on failure."""
    cfg = EMAIL_CONFIG
    context = ssl.create_default_context()
    with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"], timeout=15) as server:
        server.starttls(context=context)
        server.login(cfg["smtp_user"], cfg["smtp_password"])
        server.sendmail(cfg["email_from"], cfg["recipients"], msg.as_string())


def _cooldown_active(machine_id):
    last = last_alert_time(machine_id)
    if last is None:
        return False
    return datetime.now() - last < timedelta(minutes=ALERT_COOLDOWN_MINUTES)


def maybe_send_alert(machine_id, status, risk_percent, sensor):
    """
    Send a real email alert if:
      - email alerts are enabled,
      - the status is HIGH FAILURE RISK (or risk_percent crosses the threshold), and
      - the per-machine cooldown window has elapsed.

    Returns a small dict describing what happened, so the UI can show
    the outcome ("sent", "skipped - cooldown", "failed: <error>", etc).
    """
    if not EMAIL_ALERTS_ENABLED:
        return {"sent": False, "reason": "disabled"}

    if _cooldown_active(machine_id):
        return {"sent": False, "reason": "cooldown"}

    cfg = EMAIL_CONFIG
    if not cfg["smtp_user"] or not cfg["smtp_password"] or not cfg["recipients"]:
        log_alert(machine_id, risk_percent, status, cfg["recipients"], "failed",
                   "Missing SMTP credentials or recipients - check your .env file")
        return {"sent": False, "reason": "not_configured"}

    msg = _build_email(machine_id, status, risk_percent, sensor)
    try:
        _send_smtp(msg)
        log_alert(machine_id, risk_percent, status, cfg["recipients"], "sent")
        return {"sent": True, "reason": "ok"}
    except Exception as e:  # noqa: BLE001 - we want to log any SMTP/network failure
        log_alert(machine_id, risk_percent, status, cfg["recipients"], "failed", str(e))
        return {"sent": False, "reason": "error", "error": str(e)}
