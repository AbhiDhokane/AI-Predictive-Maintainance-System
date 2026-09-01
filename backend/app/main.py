"""
FastAPI Main Application for AI Predictive Maintenance System.
Provides RESTful APIs for real-time telemetry, ML predictions, email alerts, and historical data.
"""
import random
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import (
    CORS_ORIGINS,
    MACHINES,
    ALERT_RISK_THRESHOLD,
    EMAIL_ALERTS_ENABLED,
    EMAIL_CONFIG,
    ALERT_COOLDOWN_MINUTES,
)
from app.database import (
    ensure_schema,
    insert_reading,
    latest as db_latest,
    history as db_history,
    recent_alerts as db_recent_alerts,
    get_stats as db_get_stats,
)
from app.ml_model import predict_risk, get_model
from app.alerts import maybe_send_alert, send_test_email
from app.schemas import (
    SensorReadingCreate,
    SensorReadingResponse,
    MachineLatestStatus,
    HistoryPoint,
    PredictionRequest,
    PredictionResponse,
    AlertLogItem,
    SystemOverview,
    TestEmailRequest,
    SimulationTickRequest,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event: initialize database schema and pre-load ML model."""
    try:
        ensure_schema()
        print("Database schema verified.")
    except Exception as e:
        print(f"Warning: Failed to ensure database schema at startup: {e}")

    try:
        get_model()
        print("ML Predictive Maintenance Model loaded successfully.")
    except Exception as e:
        print(f"Warning: Failed to load ML model at startup: {e}")

    yield


app = FastAPI(
    title="AI Predictive Maintenance API",
    description="REST API for multi-machine telemetry monitoring, AI failure risk prediction, and automated email alerting.",
    version="2.0.0",
    lifespan=lifespan,
)

# Enable CORS for Vercel, localhost, and custom frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health & General Information
# ---------------------------------------------------------------------------
@app.get("/", tags=["Health"])
@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
@app.get("/api/status", tags=["Health"])
def health_check():
    """Health check endpoint for Render service monitoring."""
    return {
        "status": "healthy",
        "service": "AI Predictive Maintenance API",
        "version": "2.0.0",
        "machines": MACHINES,
        "email_alerts_enabled": EMAIL_ALERTS_ENABLED,
    }


@app.get("/api/machines", response_model=List[str], tags=["Machines"])
def list_machines():
    """List all monitored machine IDs."""
    return MACHINES


# ---------------------------------------------------------------------------
# Telemetry & Status Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/readings/latest", response_model=List[MachineLatestStatus], tags=["Telemetry"])
def get_latest_readings():
    """
    Get the latest sensor readings and real-time AI failure risk for each machine.
    """
    try:
        rows = db_latest()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query error: {str(e)}",
        )

    results = []
    for r in rows:
        pred = predict_risk(r["temperature"], r["vibration"], r["current"], r["rpm"])
        results.append(
            MachineLatestStatus(
                machine_id=r["machine_id"],
                temperature=r["temperature"],
                vibration=r["vibration"],
                current=r["current"],
                rpm=r["rpm"],
                recorded_at=r["recorded_at"],
                status=pred["status"],
                risk_percent=pred["risk_percent"],
                alert_info=None,
            )
        )
    return results


@app.get("/api/readings/history", response_model=List[HistoryPoint], tags=["Telemetry"])
def get_machine_history(
    machine_id: str = Query(..., description="Machine ID (e.g. M01)"),
    limit: int = Query(50, ge=5, le=500, description="Max number of data points"),
):
    """
    Get chronological sensor history for charts and time-series visualization.
    """
    try:
        data = db_history(machine_id, limit)
        return [HistoryPoint(**d) for d in data]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database history query error: {str(e)}",
        )


@app.post("/api/readings", response_model=MachineLatestStatus, tags=["Telemetry"])
def create_sensor_reading(payload: SensorReadingCreate):
    """
    Ingest a new sensor reading.
    Runs ML risk prediction and automatically triggers an email alert if high risk.
    """
    # 1. Evaluate ML prediction
    pred = predict_risk(
        payload.temperature,
        payload.vibration,
        payload.current,
        payload.rpm,
    )

    # 2. Insert to database
    try:
        inserted = insert_reading(
            payload.machine_id,
            payload.temperature,
            payload.vibration,
            payload.current,
            payload.rpm,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record sensor reading: {str(e)}",
        )

    # 3. Check and trigger email alert if risk exceeds threshold
    alert_result = None
    if pred["risk_percent"] >= ALERT_RISK_THRESHOLD:
        sensor_data = {
            "temperature": payload.temperature,
            "vibration": payload.vibration,
            "current": payload.current,
            "rpm": payload.rpm,
        }
        alert_result = maybe_send_alert(
            payload.machine_id,
            pred["status"],
            pred["risk_percent"],
            sensor_data,
        )

    return MachineLatestStatus(
        machine_id=payload.machine_id,
        temperature=payload.temperature,
        vibration=payload.vibration,
        current=payload.current,
        rpm=payload.rpm,
        recorded_at=inserted["recorded_at"],
        status=pred["status"],
        risk_percent=pred["risk_percent"],
        alert_info=alert_result,
    )


# ---------------------------------------------------------------------------
# Overview & Statistics
# ---------------------------------------------------------------------------
@app.get("/api/overview", response_model=SystemOverview, tags=["Overview"])
def get_system_overview():
    """Get high-level overview metrics, active machines, and latest status."""
    try:
        stats = db_get_stats()
        latest_readings = get_latest_readings()
        return SystemOverview(
            total_readings=stats["total_readings"],
            total_alerts_sent=stats["total_alerts_sent"],
            monitored_machines=MACHINES,
            alert_threshold=ALERT_RISK_THRESHOLD,
            email_alerts_enabled=EMAIL_ALERTS_ENABLED,
            machines=latest_readings,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error compiling overview: {str(e)}",
        )


# ---------------------------------------------------------------------------
# ML Prediction
# ---------------------------------------------------------------------------
@app.post("/api/predict", response_model=PredictionResponse, tags=["AI Prediction"])
def predict(payload: PredictionRequest):
    """Direct inference endpoint to evaluate machine failure risk given raw telemetry."""
    try:
        result = predict_risk(payload.temperature, payload.vibration, payload.current, payload.rpm)
        return PredictionResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference error: {str(e)}",
        )


# ---------------------------------------------------------------------------
# Alerts & Notification Logs
# ---------------------------------------------------------------------------
@app.get("/api/alerts/recent", response_model=List[AlertLogItem], tags=["Alerts"])
def get_recent_alerts(limit: int = Query(20, ge=1, le=100)):
    """Fetch the latest alert history records."""
    try:
        logs = db_recent_alerts(limit)
        return [AlertLogItem(**l) for l in logs]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching alerts: {str(e)}",
        )


@app.post("/api/alerts/test", tags=["Alerts"])
def trigger_test_alert(payload: Optional[TestEmailRequest] = None):
    """Trigger a test email notification to verify SMTP settings."""
    recipient = payload.recipient if payload else None
    result = send_test_email(recipient)
    if not result.get("sent"):
        return JSONResponse(status_code=400, content=result)
    return result


# ---------------------------------------------------------------------------
# Simulation Triggers (For live web demos & testing)
# ---------------------------------------------------------------------------
@app.post("/api/simulator/tick", tags=["Simulator"])
def simulate_cycle(payload: Optional[SimulationTickRequest] = None):
    """
    Generate one cycle of simulated sensor readings across all machines.
    Useful for testing the dashboard live without a background daemon.
    """
    abnormal_chance = payload.abnormal_chance if payload else 0.15
    results = []

    for mid in MACHINES:
        temperature = random.uniform(50, 70)
        vibration = random.uniform(1, 2.8)
        current = random.uniform(4, 7)
        rpm = random.randint(1400, 1750)

        # Inject anomaly if roll matches abnormal chance
        if random.random() < abnormal_chance:
            temperature = random.uniform(82, 98)
            vibration = random.uniform(4.5, 6.8)
            current = random.uniform(8.5, 11.8)
            rpm = random.randint(950, 1280)

        reading = create_sensor_reading(
            SensorReadingCreate(
                machine_id=mid,
                temperature=round(temperature, 2),
                vibration=round(vibration, 2),
                current=round(current, 2),
                rpm=rpm,
            )
        )
        results.append(reading)

    return {"message": "Simulation tick generated", "readings": results}


@app.post("/api/simulator/hazard", tags=["Simulator"])
def trigger_hazard(machine_id: str = Query(..., description="Target machine ID (e.g. M01)")):
    """
    Force a high-risk anomaly event on a specific machine to test alerts immediately.
    """
    if machine_id not in MACHINES:
        raise HTTPException(status_code=400, detail=f"Machine {machine_id} is not in monitored list.")

    reading = create_sensor_reading(
        SensorReadingCreate(
            machine_id=machine_id,
            temperature=round(random.uniform(88, 98), 2),
            vibration=round(random.uniform(5.2, 7.1), 2),
            current=round(random.uniform(9.5, 12.0), 2),
            rpm=random.randint(900, 1200),
        )
    )
    return {"message": f"Hazard injected on {machine_id}", "reading": reading}


@app.post("/api/simulator/normalize", tags=["Simulator"])
def normalize_machine(machine_id: str = Query(..., description="Target machine ID (e.g. M03)")):
    """
    Inject a healthy, normal reading on a machine to restore it from failure state.
    """
    if machine_id not in MACHINES:
        raise HTTPException(status_code=400, detail=f"Machine {machine_id} is not in monitored list.")

    reading = create_sensor_reading(
        SensorReadingCreate(
            machine_id=machine_id,
            temperature=round(random.uniform(58, 68), 2),
            vibration=round(random.uniform(1.2, 2.2), 2),
            current=round(random.uniform(4.5, 6.2), 2),
            rpm=random.randint(1550, 1720),
        )
    )
    return {"message": f"Machine {machine_id} telemetry restored to normal healthy range.", "reading": reading}
