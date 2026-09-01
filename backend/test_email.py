"""
Standalone sanity check for email alert delivery.
Run to verify SMTP connectivity and login credentials.
"""
from app.config import EMAIL_CONFIG, EMAIL_ALERTS_ENABLED
from app.database import ensure_schema
from app.alerts import maybe_send_alert

if __name__ == "__main__":
    print("AI Predictive Maintenance - SMTP Delivery Check")
    print("-" * 50)
    print("EMAIL_ALERTS_ENABLED:", EMAIL_ALERTS_ENABLED)
    print("SMTP host/port:", EMAIL_CONFIG["smtp_host"], EMAIL_CONFIG["smtp_port"])
    print("From:", EMAIL_CONFIG["email_from"])
    print("Recipients:", EMAIL_CONFIG["recipients"])
    print("-" * 50)

    try:
        ensure_schema()
    except Exception as e:
        print("Note: Could not connect to DB for logging, but will still test SMTP:", e)

    fake_sensor = {"temperature": 93.8, "vibration": 6.2, "current": 10.4, "rpm": 1020}
    result = maybe_send_alert("M01-TEST", "HIGH FAILURE RISK", 91.2, fake_sensor)

    print("\nResult:", result)
    if result.get("sent"):
        print("\n✅ Test email sent successfully! Please check your inbox.")
    else:
        print(f"\n❌ Email NOT sent. Reason: {result.get('reason')}")
        if "error" in result:
            print("Error detail:", result["error"])
