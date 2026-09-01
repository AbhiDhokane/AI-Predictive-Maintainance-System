"""
Email Alert Service for AI Predictive Maintenance System.
Supports both modern HTTPS Email APIs (Resend, Brevo) and standard SMTP (Gmail, Outlook).
HTTPS APIs bypass cloud firewall restrictions where SMTP ports (25, 465, 587) are blocked.
"""
import smtplib
import socket
import ssl
import json
import urllib.request
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


def _build_email_contents(machine_id: str, status: str, risk_percent: float, sensor: Dict[str, Any]):
    subject = f"🚨 [CRITICAL ALERT] {machine_id} - {status} ({risk_percent:.1f}% Failure Risk)"
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
    return subject, plain_text, html_content


def _send_via_resend(api_key: str, recipients: List[str], subject: str, html: str, text: str):
    """Dispatch email using Resend HTTPS API (Port 443 - works on Render Free Tier)."""
    cfg = EMAIL_CONFIG
    from_addr = "AI Predictive Maintenance <onboarding@resend.dev>"
    if cfg.get("email_from") and "@gmail.com" not in cfg.get("email_from", "") and "@" in cfg.get("email_from", ""):
        from_addr = cfg["email_from"]

    def _post_resend(to_list):
        payload = {
            "from": from_addr,
            "to": to_list,
            "subject": subject,
            "html": html,
            "text": text,
        }
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "AIPredictiveMaintenance/2.0",
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    try:
        return _post_resend(recipients)
    except urllib.error.HTTPError as e:
        err_raw = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_raw)
            err_msg = err_json.get("message", err_raw)
        except Exception:
            err_msg = err_raw

        # If sandbox restriction on multiple recipients or unverified address, attempt each recipient individually
        if e.code in (403, 422) and len(recipients) > 1:
            delivered = []
            for r in recipients:
                try:
                    _post_resend([r])
                    delivered.append(r)
                except Exception:
                    pass
            if delivered:
                return {"sent": True, "delivered_to": delivered, "note": f"Delivered to verified sandbox recipient(s): {', '.join(delivered)}"}

        raise RuntimeError(f"Resend API ({e.code}): {err_msg}")
    except Exception as e:
        raise RuntimeError(f"Resend Dispatch Error: {str(e)}")


def _send_via_brevo(api_key: str, recipients: List[str], subject: str, html: str, text: str):
    """Dispatch email using Brevo HTTPS API (Port 443)."""
    cfg = EMAIL_CONFIG
    payload = {
        "sender": {"name": "AI Predictive Maintenance", "email": cfg.get("email_from") or "alerts@predictive-maintenance.com"},
        "to": [{"email": r} for r in recipients],
        "subject": subject,
        "htmlContent": html,
        "textContent": text,
    }
    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _send_via_smtp(recipients: List[str], subject: str, html: str, text: str):
    """Dispatch email over SMTP with dual-port fallback (465 SSL <-> 587 STARTTLS)."""
    cfg = EMAIL_CONFIG
    msg = MIMEMultipart("alternative")
    msg["From"] = cfg["email_from"] or cfg["smtp_user"]
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    context = ssl.create_default_context()
    last_err = None

    # Try port 465 first (often allowed where 587 is blocked)
    for port in [465, 587]:
        try:
            if port == 465:
                with IPv4SMTP_SSL(cfg["smtp_host"], port, context=context, timeout=8) as server:
                    server.login(cfg["smtp_user"], cfg["smtp_password"])
                    server.sendmail(cfg["email_from"] or cfg["smtp_user"], recipients, msg.as_string())
                    return True
            else:
                with IPv4SMTP(cfg["smtp_host"], port, timeout=8) as server:
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
        err_str = str(last_err)
        if "timed out" in err_str.lower() or "101" in err_str:
            raise RuntimeError(
                "SMTP timed out. Note: Render Free Tier blocks outbound SMTP ports 587/465. "
                "For instant email on Render, add a free RESEND_API_KEY in Render Environment Variables."
            )
        raise last_err


def _dispatch_email(recipients: List[str], subject: str, html: str, text: str):
    """
    Intelligent email dispatcher:
    1. If RESEND_API_KEY is configured -> sends over HTTPS (Port 443)
    2. If BREVO_API_KEY is configured  -> sends over HTTPS (Port 443)
    3. Else                            -> sends over SMTP (Port 465/587)
    """
    cfg = EMAIL_CONFIG
    if cfg.get("resend_api_key"):
        return _send_via_resend(cfg["resend_api_key"], recipients, subject, html, text)
    elif cfg.get("brevo_api_key"):
        return _send_via_brevo(cfg["brevo_api_key"], recipients, subject, html, text)
    else:
        return _send_via_smtp(recipients, subject, html, text)


def is_cooldown_active(machine_id: str) -> bool:
    """Check if cooldown is active for this machine."""
    last = last_alert_time(machine_id)
    if last is None:
        return False
    return datetime.now() - last < timedelta(minutes=ALERT_COOLDOWN_MINUTES)


def maybe_send_alert(machine_id: str, status: str, risk_percent: float, sensor: Dict[str, Any], email_enabled: Optional[bool] = None) -> Dict[str, Any]:
    """Evaluate risk threshold and send alert email if needed."""
    alerts_on = email_enabled if email_enabled is not None else EMAIL_ALERTS_ENABLED
    if not alerts_on:
        return {"sent": False, "reason": "disabled", "message": "Email alerts are currently turned OFF by operator."}

    if risk_percent < ALERT_RISK_THRESHOLD:
        return {"sent": False, "reason": "below_threshold"}

    if is_cooldown_active(machine_id):
        return {"sent": False, "reason": "cooldown", "message": f"Cooldown active for {machine_id}."}

    cfg = EMAIL_CONFIG
    recipients = cfg.get("recipients", [])
    if not recipients:
        msg = "Missing ALERT_RECIPIENTS in configuration."
        log_alert(machine_id, risk_percent, status, recipients, "failed", msg)
        return {"sent": False, "reason": "not_configured", "error": msg}

    subject, plain_text, html_content = _build_email_contents(machine_id, status, risk_percent, sensor)
    try:
        _dispatch_email(recipients, subject, html_content, plain_text)
        log_alert(machine_id, risk_percent, status, recipients, "sent")
        return {"sent": True, "reason": "ok", "message": f"Alert sent to {', '.join(recipients)}"}
    except Exception as e:
        error_msg = str(e)
        log_alert(machine_id, risk_percent, status, recipients, "failed", error_msg)
        return {"sent": False, "reason": "error", "error": error_msg}


def send_test_email(recipient: Optional[str] = None) -> Dict[str, Any]:
    """Trigger test email notification."""
    fake_sensor = {"temperature": 94.2, "vibration": 6.1, "current": 10.5, "rpm": 1020}
    cfg = EMAIL_CONFIG
    recipients = [recipient] if recipient else cfg.get("recipients", [])

    if not recipients:
        return {"sent": False, "reason": "not_configured", "error": "No recipient specified."}

    subject, plain_text, html_content = _build_email_contents("M01-TEST", "HIGH FAILURE RISK (TEST)", 92.5, fake_sensor)
    try:
        _dispatch_email(recipients, subject, html_content, plain_text)
        log_alert("M01-TEST", 92.5, "HIGH FAILURE RISK (TEST)", recipients, "sent")
        return {"sent": True, "reason": "ok", "message": f"Test alert sent to {', '.join(recipients)}"}
    except Exception as e:
        error_msg = str(e)
        log_alert("M01-TEST", 92.5, "HIGH FAILURE RISK (TEST)", recipients, "failed", error_msg)
        return {"sent": False, "reason": "error", "error": error_msg}
