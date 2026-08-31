import time

import joblib
import pandas as pd
import plotly.express as px
import streamlit as st

from config import MACHINES, ALERT_RISK_THRESHOLD, EMAIL_ALERTS_ENABLED, EMAIL_CONFIG
from database import ensure_schema, latest, history, recent_alerts
from alerts import maybe_send_alert

st.set_page_config(page_title="AI Predictive Maintenance", page_icon="\U0001F3ED", layout="wide")

ensure_schema()
model = joblib.load("model/failure_model.pkl")

st.title("\U0001F3ED AI Predictive Maintenance System")

with st.sidebar:
    st.subheader("\U0001F504 Auto-refresh")
    auto_refresh = st.toggle("Auto-refresh dashboard", value=True)
    refresh_seconds = st.slider("Refresh every (seconds)", 3, 60, 5, disabled=not auto_refresh)
    if auto_refresh:
        st.caption(f"Live - updating every {refresh_seconds}s")
    else:
        st.caption("Paused - use the Refresh button below")

    st.subheader("\u2709\ufe0f Email Alerts")
    if EMAIL_ALERTS_ENABLED:
        st.success("Enabled")
        recipients = EMAIL_CONFIG["recipients"]
        st.caption(f"Sends to: {', '.join(recipients) if recipients else '(none configured)'}")
        st.caption(f"Trigger threshold: risk \u2265 {ALERT_RISK_THRESHOLD}%")
    else:
        st.warning("Disabled (set EMAIL_ALERTS_ENABLED=true in .env)")

rows = latest()
if not rows:
    st.warning("No readings yet. Start sensor_simulator.py first.")
    st.stop()

df = pd.DataFrame(rows, columns=["machine_id", "temperature", "vibration", "current", "rpm", "recorded_at"])


def predict(row):
    features = [[row.temperature, row.vibration, row.current, row.rpm]]
    predicted_class = int(model.predict(features)[0])
    probabilities = model.predict_proba(features)[0]
    status = ["NORMAL", "WARNING", "HIGH FAILURE RISK"][predicted_class]
    risk_percent = probabilities[2] * 100
    return status, risk_percent


df[["status", "risk"]] = df.apply(lambda r: pd.Series(predict(r)), axis=1)

columns = st.columns(len(df))
for col, (_, row) in zip(columns, df.iterrows()):
    with col:
        st.subheader(row.machine_id)
        st.metric("Temperature", f"{row.temperature:.1f} \u00b0C")
        st.metric("Vibration", f"{row.vibration:.2f} mm/s")
        st.metric("Current", f"{row.current:.2f} A")
        st.metric("RPM", f"{row.rpm:.0f}")

        status_widget = st.success if row.status == "NORMAL" else st.warning if row.status == "WARNING" else st.error
        status_widget(row.status)
        st.write(f"AI failure risk: **{row.risk:.1f}%**")

        if row.risk >= ALERT_RISK_THRESHOLD:
            st.error("\U0001F6A8 Maintenance recommended")
            sensor = {
                "temperature": row.temperature,
                "vibration": row.vibration,
                "current": row.current,
                "rpm": row.rpm,
            }
            result = maybe_send_alert(row.machine_id, row.status, row.risk, sensor)
            if result["sent"]:
                st.info("\U0001F4E7 Alert email sent to maintenance team")
            elif result["reason"] == "cooldown":
                st.caption("\U0001F4E7 Alert already sent recently (cooldown active)")
            elif result["reason"] == "disabled":
                st.caption("\U0001F4E7 Email alerts are disabled")
            elif result["reason"] == "not_configured":
                st.caption("\u26a0\ufe0f Email not sent - SMTP not configured (see .env)")
            else:
                st.caption(f"\u26a0\ufe0f Email failed to send: {result.get('error', 'unknown error')}")

st.subheader("Sensor History")
selected_machine = st.selectbox("Machine", MACHINES)
hist = history(selected_machine)
if hist:
    hist_df = pd.DataFrame(
        hist, columns=["temperature", "vibration", "current", "rpm", "recorded_at"]
    ).sort_values("recorded_at")
    metric = st.selectbox("Sensor", ["temperature", "vibration", "current", "rpm"])
    st.plotly_chart(
        px.line(hist_df, x="recorded_at", y=metric, title=f"{selected_machine} - {metric}"),
        use_container_width=True,
    )

st.subheader("\U0001F4EC Recent Alert History")
alerts = recent_alerts(20)
if alerts:
    alerts_df = pd.DataFrame(
        alerts,
        columns=["machine_id", "risk_percent", "status", "recipients", "email_status", "error_message", "sent_at"],
    )
    st.dataframe(alerts_df, use_container_width=True, hide_index=True)
else:
    st.caption("No alerts sent yet.")

if st.button("\U0001F504 Refresh now"):
    st.rerun()

if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()
