"""
Standalone sanity check for your email setup.

Run this after filling in .env to confirm SMTP login and delivery work
BEFORE relying on it inside the Streamlit app:

    python test_email.py
"""
from database import ensure_schema
from alerts import maybe_send_alert
from config import EMAIL_CONFIG, EMAIL_ALERTS_ENABLED

print("EMAIL_ALERTS_ENABLED:", EMAIL_ALERTS_ENABLED)
print("SMTP host/port:", EMAIL_CONFIG["smtp_host"], EMAIL_CONFIG["smtp_port"])
print("From:", EMAIL_CONFIG["email_from"])
print("Recipients:", EMAIL_CONFIG["recipients"])
print()

ensure_schema()

fake_sensor = {"temperature": 92.5, "vibration": 5.8, "current": 9.7, "rpm": 1050}
result = maybe_send_alert("M01-TEST", "HIGH FAILURE RISK", 87.3, fake_sensor)

print("Result:", result)
if result["sent"]:
    print("\n\u2705 Test email sent successfully - check the recipient inbox.")
else:
    print(f"\n\u274c Email NOT sent. Reason: {result['reason']}")
    if "error" in result:
        print("Error detail:", result["error"])
