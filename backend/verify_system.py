"""
End-to-End System Verification Script for Backend.
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60, flush=True)
print("  AI Predictive Maintenance - System Verification", flush=True)
print("=" * 60, flush=True)

# 1. Config Check
print("\n1. Testing Configuration Loader...", flush=True)
from app.config import MACHINES, ALERT_RISK_THRESHOLD, EMAIL_ALERTS_ENABLED, DB_CONFIG
print(f"   - Monitored Machines: {MACHINES}", flush=True)
print(f"   - Alert Risk Threshold: {ALERT_RISK_THRESHOLD}%", flush=True)
print(f"   - Email Alerts Enabled: {EMAIL_ALERTS_ENABLED}", flush=True)
print("   ✅ Config loaded successfully.", flush=True)

# 2. Database & Schema Check
print("\n2. Testing PostgreSQL Database & Schema...", flush=True)
from app.database import ensure_schema, get_stats, latest, history, recent_alerts
ensure_schema()
stats = get_stats()
print(f"   - Total Sensor Readings in DB: {stats['total_readings']}", flush=True)
print(f"   - Total Sent Alerts in DB: {stats['total_alerts_sent']}", flush=True)
print("   ✅ Database schema and queries working.", flush=True)

# 3. Machine Learning Model Check
print("\n3. Testing ML Failure Risk Classifier...", flush=True)
from app.ml_model import predict_risk
# Normal reading test
normal_pred = predict_risk(temperature=60.0, vibration=1.8, current=5.0, rpm=1600)
print(f"   - Normal sample -> Status: {normal_pred['status']} (Risk: {normal_pred['risk_percent']}%)", flush=True)
assert normal_pred['status'] == 'NORMAL'

# High risk anomaly test
hazard_pred = predict_risk(temperature=95.0, vibration=6.2, current=10.5, rpm=1050)
print(f"   - Hazard sample -> Status: {hazard_pred['status']} (Risk: {hazard_pred['risk_percent']}%)", flush=True)
assert hazard_pred['status'] == 'HIGH FAILURE RISK'
assert hazard_pred['risk_percent'] > 75
print("   ✅ ML Model predictions accurate.", flush=True)

# 4. FastAPI Endpoints Check
print("\n4. Testing FastAPI Application...", flush=True)
from app.main import app, health_check, list_machines, get_system_overview

hc = health_check()
print(f"   - Health Check: {hc['status']} ({hc['service']})", flush=True)
assert hc['status'] == 'healthy'

machines = list_machines()
print(f"   - Machine List: {machines}", flush=True)
assert len(machines) >= 3

overview = get_system_overview()
print(f"   - Fleet Overview: {len(overview.machines)} machines monitored", flush=True)
print("   ✅ FastAPI routes initialized and functioning.", flush=True)

# 5. History Query Check
print("\n5. Testing Time-Series Telemetry History...", flush=True)
from app.main import get_machine_history
hist = get_machine_history(machine_id="M01", limit=10)
print(f"   - Retrieved {len(hist)} chronological telemetry points for M01", flush=True)
print("   ✅ Telemetry history query functioning.", flush=True)

print("\n" + "=" * 60, flush=True)
print("  🎉 ALL VERIFICATION CHECKS PASSED SUCCESSFULLY!", flush=True)
print("=" * 60, flush=True)
