"""
Email Alert Service for AI Predictive Maintenance System.
Handles SMTP notifications with HTML formatting, cooldown enforcement, and database logging.
Forces IPv4 socket resolution to prevent '[Errno 101] Network is unreachable' on cloud hosts.
"""
import smtplib
import socket
import ssl
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional, List

from app.config import (
    EMAIL_CONFIG,
    EMAIL_ALERTS_ENABLED,
    ALERT_COOLDOWN_MINUTES,
    ALERT_RISK_THRESHOLD,
)
from app.database import last_alert_time, log_alert


class IPv4SMTP(smtplib.SMTP):
    """SMTP client forcing IPv4 to prevent unreachable network errors on cloud containers."""
    def _get_socket(self, host, port, timeout):
        try:
            res = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
            target = res[0][4]
        except Exception:
            target = (host, port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(target)
        return sock


class IPv4SMTP_SSL(smtplib.SMTP_SSL):
    """SMTP SSL client forcing IPv4 socket resolution."""
    def _get_socket(self, host, port, timeout):
        try:
            res = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
            target = res[0][4]
        except Exception:
            target = (host, port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(target)
        return self.context.wrap_socket(sock, server_hostname=self._host)


def _build_email(machine_id: str, status: str, risk_percent: float, sensor: Dict[str, Any], recipients: List[str]) -> MIMEMultipart:
    cfg = EMAIL_CONFIG
    subject = f"🚨 [CRITICAL ALERT] {machine_id} - {status} ({risk_percent:.1f}% Failure Risk)"
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Plain text fallback
    plain_text = f"""\
AI Predictive Maintenance Alert
=================================
Machine ID:    {machine_id}
Status:        {status}
Failure Risk:  {risk_percent:.1f}%
Detected At:   {timestamp_str}

Telemetry Readings:
- Temperature: {sensor.get('temperature', 0):.1f} °C
- Vibration:   {sensor.get('vibration', 0):.2f} mm/s
- Current:     {sensor.get('current', 0):.2f} A
- RPM:         {sensor.get('rpm', 0):.0f}

Recommended Action:
Schedule immediate mechanical and thermal inspection for Machine {machine_id}.
    """

    # Modern HTML email
    html_content = f"""\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }}
    .card {{ max-width: 580px; margin: 0 auto; background-color: #1e293b; border-radius: 12px; border: 1px solid #334155; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
    .header {{ background: linear-gradient(135deg, #e11d48, #be123c); padding: 24px; text-align: center; color: #ffffff; }}
    .header h1 {{ margin: 0; font-size: 22px; font-weight: 700; }}
    .badge {{ display: inline-block; background-color: #ffffff; color: #be123c; font-weight: 800; font-size: 13px; padding: 4px 12px; border-radius: 9999px; margin-top: 8px; }}
    .content {{ padding: 24px; }}
    .risk-banner {{ background-color: rgba(225, 29, 72, 0.15); border: 1px solid #e11d48; padding: 16px; border-radius: 8px; margin-bottom: 20px; }}
    .footer {{ padding: 16px 24px; background-color: #0f172a; font-size: 12px; color: #64748b; text-align: center; border-top: 1px solid #334155; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h1>High Failure Risk Detected</h1>
      <div class="badge">Machine {machine_id}</div>
    </div>
    <div class="content">
      <div class="risk-banner">
        <strong style="color: #f43f5e; font-size: 16px;">AI Predicted Risk: {risk_percent:.1f}%</strong>
        <div style="color: #cbd5e1; font-size: 13px; margin-top: 4px;">Immediate inspection recommended to prevent mechanical breakdown.</div>
      </div>

      <div style="font-size: 14px; color: #94a3b8;">Recorded Telemetry at {timestamp_str}:</div>
      <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
        <tr>
          <td style="padding: 8px; border-bottom: 1px solid #334155; color: #94a3b8;">Temperature</td>
          <td style="padding: 8px; border-bottom: 1px solid #334155; font-weight: bold; color: #f8fafc; text-align: right;">{sensor.get('temperature', 0):.1f} °C</td>
        </tr>
        <tr>
          <td style="padding: 8px; border-bottom: 1px solid #334155; color: #94a3b8;">Vibration</td>
          <td style="padding: 8px; border-bottom: 1px solid #334155; font-weight: bold; color: #f8fafc; text-align: right;">{sensor.get('vibration', 0):.2f} mm/s</td>
        </tr>
        <tr>
          <td style="padding: 8px; border-bottom: 1px solid #334155; color: #94a3b8;">Current</td>
          <td style="padding: 8px; border-bottom: 1px solid #334155; font-weight: bold; color: #f8fafc; text-align: right;">{sensor.get('current', 0):.2f} A</td>
        </tr>
        <tr>
          <td style="padding: 8px; color: #94a3b8;">RPM</td>
          <td style="padding: 8px; font-weight: bold; color: #f8fafc; text-align: right;">{sensor.get('rpm', 0):.0f} RPM</td>
        </tr>
      </table>
    </div>
    <div class="footer">
      AI Predictive Maintenance System • Automated Alert Notification
    </div>
  </div>
</body>
</html>
    """

    msg = MIMEMultipart("alternative")
    msg["From"] = cfg["email_from"] or cfg["smtp_user"]
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject

    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_content, "html"))
    return msg


def _send_smtp_dispatch(msg: MIMEMultipart, recipients: List[str]):
    """
    Dispatches email via IPv4 SMTP with dual-port fallback (Port 587 STARTTLS <-> Port 465 SSL)
    to guarantee delivery across cloud firewall and networking constraints.
    """
    cfg = EMAIL_CONFIG
    context = ssl.create_default_context()
    last_err = None

    # Primary attempt with configured port
    primary_port = cfg.get("smtp_port", 587)
    ports_to_try = [primary_port]
    # Add alternative port fallback (465 if 587, or 587 if 465)
    if primary_port == 587:
        ports_to_try.append(465)
    elif primary_port == 465:
        ports_to_try.append(587)

    for port in ports_to_try:
        try:
            if port == 465:
                with IPv4SMTP_SSL(cfg["smtp_host"], port, context=context, timeout=12) as server:
                    server.login(cfg["smtp_user"], cfg["smtp_password"])
                    server.sendmail(cfg["email_from"] or cfg["smtp_user"], recipients, msg.as_string())
                    return True
            else:
                with IPv4SMTP(cfg["smtp_host"], port, timeout=12) as server:
                    server.ehlo()
                    server.starttls(context=context)
                    server.ehlo()
                    server.login(cfg["smtp_user"], cfg["smtp_password"])
                    server.sendmail(cfg["email_from"] or cfg["smtp_user"], recipients, msg.as_string())
                    return True
        except Exception as e:
            last_err = e
            continue

    if last_err:
        raise last_err


def is_cooldown_active(machine_id: str) -> bool:
    """Check if the cooldown period has elapsed since the last sent email for this machine."""
    last = last_alert_time(machine_id)
    if last is None:
        return False
    return datetime.now() - last < timedelta(minutes=ALERT_COOLDOWN_MINUTES)


def maybe_send_alert(machine_id: str, status: str, risk_percent: float, sensor: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send an email alert if:
      - Email alerts are enabled in config
      - Risk percent is at/above ALERT_RISK_THRESHOLD
      - Cooldown window has elapsed
    """
    if not EMAIL_ALERTS_ENABLED:
        return {"sent": False, "reason": "disabled", "message": "Email alerts are disabled in configuration."}

    if risk_percent < ALERT_RISK_THRESHOLD:
        return {"sent": False, "reason": "below_threshold", "message": f"Risk ({risk_percent}%) below threshold ({ALERT_RISK_THRESHOLD}%)."}

    if is_cooldown_active(machine_id):
        return {"sent": False, "reason": "cooldown", "message": f"Alert cooldown active for {machine_id} (last alert sent within {ALERT_COOLDOWN_MINUTES} mins)."}

    cfg = EMAIL_CONFIG
    recipients = cfg.get("recipients", [])
    if not cfg.get("smtp_user") or not cfg.get("smtp_password") or not recipients:
        msg = "Missing SMTP credentials or recipients in .env configuration."
        log_alert(machine_id, risk_percent, status, recipients, "failed", msg)
        return {"sent": False, "reason": "not_configured", "error": msg}

    msg = _build_email(machine_id, status, risk_percent, sensor, recipients)
    try:
        _send_smtp_dispatch(msg, recipients)
        log_alert(machine_id, risk_percent, status, recipients, "sent")
        return {"sent": True, "reason": "ok", "message": f"Alert successfully sent to {', '.join(recipients)}"}
    except Exception as e:
        error_msg = str(e)
        log_alert(machine_id, risk_percent, status, recipients, "failed", error_msg)
        return {"sent": False, "reason": "error", "error": error_msg}


def send_test_email(recipient: Optional[str] = None) -> Dict[str, Any]:
    """Trigger a manual test email to verify SMTP delivery."""
    fake_sensor = {"temperature": 94.2, "vibration": 6.1, "current": 10.5, "rpm": 1020}
    cfg = EMAIL_CONFIG
    recipients = [recipient] if recipient else cfg.get("recipients", [])

    if not cfg.get("smtp_user") or not cfg.get("smtp_password") or not recipients:
        return {"sent": False, "reason": "not_configured", "error": "SMTP credentials or recipients not set."}

    msg = _build_email("M01-TEST", "HIGH FAILURE RISK (TEST)", 92.5, fake_sensor, recipients)

    try:
        _send_smtp_dispatch(msg, recipients)
        log_alert("M01-TEST", 92.5, "HIGH FAILURE RISK (TEST)", recipients, "sent")
        return {"sent": True, "reason": "ok", "message": f"Test alert sent to {', '.join(recipients)}"}
    except Exception as e:
        error_msg = str(e)
        log_alert("M01-TEST", 92.5, "HIGH FAILURE RISK (TEST)", recipients, "failed", error_msg)
        return {"sent": False, "reason": "error", "error": error_msg}
