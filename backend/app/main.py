"""
FastAPI Main Application for AI Predictive Maintenance System.
Features autonomous background telemetry streaming, real-time ML risk prediction,
automatic emergency safety lockout (trip) on hazard detection, and SMTP/HTTPS alerting.
"""
import asyncio
import random
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any

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

# ---------------------------------------------------------------------------
# In-Memory Machine State & Physical Telemetry Controllers
# ---------------------------------------------------------------------------
def _init_cycles_for(mid: str, idx: int) -> int:
    """Stagger initial autonomous faults across machines (20s - 90s)."""
    base = (idx + 1) * 5
    return random.randint(base, base + 4)


MACHINE_CONTROLLERS: Dict[str, Dict[str, Any]] = {
    m: {
        "operational_state": "RUNNING",  # "RUNNING" or "TRIPPED_STOPPED"
        "temp": round(random.uniform(58.0, 66.0), 2),
        "vib": round(random.uniform(1.2, 1.8), 2),
        "curr": round(random.uniform(4.5, 5.5), 2),
        "rpm": random.randint(1550, 1720),
        "cycles": 0,
        "cycles_to_fault": _init_cycles_for(m, i),
    }
    for i, m in enumerate(MACHINES)
}


def _step_machine_telemetry(mid: str) -> Dict[str, Any]:
    """
    Executes one physical simulation step for a machine.
    If tripped, keeps machine halted with cooling temperature and 0 RPM until user heals it.
    If running, generates realistic smooth multi-stage physical degradation -> failure trip.
    """
    ctrl = MACHINE_CONTROLLERS.setdefault(mid, {
        "operational_state": "RUNNING",
        "temp": 62.0,
        "vib": 1.4,
        "curr": 4.8,
        "rpm": 1650,
        "cycles": 0,
        "cycles_to_fault": random.randint(8, 14),
    })

    # Case 1: Machine is in Safety Shutdown / Lockout
    if ctrl["operational_state"] == "TRIPPED_STOPPED":
        # Machine is stopped: cooldown towards ambient 30°C, 0 RPM, 0 Current
        ctrl["temp"] = round(max(30.0, ctrl["temp"] - 1.5), 2)
        ctrl["vib"] = round(random.uniform(0.02, 0.06), 2)
        ctrl["curr"] = 0.0
        ctrl["rpm"] = 0

        return create_sensor_reading(
            SensorReadingCreate(
                machine_id=mid,
                temperature=ctrl["temp"],
                vibration=ctrl["vib"],
                current=ctrl["curr"],
                rpm=ctrl["rpm"],
            )
        )

    # Case 2: Machine is Active & Running
    ctrl["cycles"] += 1
    remaining = ctrl["cycles_to_fault"] - ctrl["cycles"]

    # Stage 5: Critical Failure Anomaly Spike -> Trigger Automatic Safety Trip!
    if remaining <= 0:
        ctrl["temp"] = round(random.uniform(94.5, 98.5), 2)
        ctrl["vib"] = round(random.uniform(6.2, 7.6), 2)
        ctrl["curr"] = round(random.uniform(10.8, 12.6), 2)
        ctrl["rpm"] = random.randint(920, 1080)
        
        # Automatic Emergency Trip Lockout
        ctrl["operational_state"] = "TRIPPED_STOPPED"
        print(f"🚨 [SAFETY TRIP] High failure risk detected on {mid}! Machine automatically shut down.")

    # Stage 4: Severe Anomaly Build-up (1 cycle before trip)
    elif remaining == 1:
        ctrl["temp"] = round(random.uniform(89.0, 93.5), 2)
        ctrl["vib"] = round(random.uniform(4.9, 5.8), 2)
        ctrl["curr"] = round(random.uniform(9.0, 10.5), 2)
        ctrl["rpm"] = random.randint(1180, 1300)

    # Stage 3: Elevated Warning (2-3 cycles before trip)
    elif remaining <= 3:
        ctrl["temp"] = round(random.uniform(82.0, 87.5), 2)
        ctrl["vib"] = round(random.uniform(3.6, 4.6), 2)
        ctrl["curr"] = round(random.uniform(7.5, 8.8), 2)
        ctrl["rpm"] = random.randint(1320, 1450)

    # Stage 2: Mild Thermal & Vibration Rise (4-5 cycles before trip)
    elif remaining <= 5:
        ctrl["temp"] = round(random.uniform(72.0, 78.5), 2)
        ctrl["vib"] = round(random.uniform(2.3, 3.2), 2)
        ctrl["curr"] = round(random.uniform(5.8, 6.9), 2)
        ctrl["rpm"] = random.randint(1480, 1580)

    # Stage 1: Healthy Baseline with subtle physical noise
    else:
        ctrl["temp"] = round(max(56.0, min(68.0, ctrl["temp"] + random.uniform(-0.6, 0.6))), 2)
        ctrl["vib"] = round(max(1.0, min(1.8, ctrl["vib"] + random.uniform(-0.08, 0.08))), 2)
        ctrl["curr"] = round(max(4.2, min(5.4, ctrl["curr"] + random.uniform(-0.1, 0.1))), 2)
        ctrl["rpm"] = int(max(1580, min(1740, ctrl["rpm"] + random.randint(-15, 15))))

    return create_sensor_reading(
        SensorReadingCreate(
            machine_id=mid,
            temperature=ctrl["temp"],
            vibration=ctrl["vib"],
            current=ctrl["curr"],
            rpm=ctrl["rpm"],
        )
    )


def generate_autonomous_cycle():
    """Generates 1 continuous telemetry reading for each monitored machine."""
    for mid in MACHINES:
        try:
            _step_machine_telemetry(mid)
        except Exception as e:
            print(f"Telemetry step error for {mid}: {e}")


async def telemetry_background_worker():
    """Autonomous background loop generating continuous IoT readings every 5 seconds."""
    await asyncio.sleep(2)  # Initial wait on startup
    while True:
        try:
            generate_autonomous_cycle()
        except Exception as e:
            print(f"Autonomous background telemetry error: {e}")
        await asyncio.sleep(5)


# ---------------------------------------------------------------------------
# FastAPI Application Setup & Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event: initialize database schema, pre-load ML model, and start telemetry generator."""
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

    # Launch background autonomous telemetry generator
    task = asyncio.create_task(telemetry_background_worker())
    yield
    task.cancel()


app = FastAPI(
    title="AI Predictive Maintenance API",
    description="REST API for multi-machine telemetry monitoring, AI failure risk prediction, autonomous telemetry, and automated email alerting.",
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
    """Health check endpoint for service monitoring."""
    return {
        "status": "healthy",
        "service": "AI Predictive Maintenance API",
        "version": "2.0.0",
        "machines": MACHINES,
        "email_alerts_enabled": EMAIL_ALERTS_ENABLED,
        "autonomous_generator": "active (5s interval)",
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
        ctrl = MACHINE_CONTROLLERS.get(r["machine_id"], {})
        op_state = ctrl.get("operational_state", "RUNNING")
        
        # If machine is stopped, display status clearly
        display_status = "EMERGENCY STOPPED" if (op_state == "TRIPPED_STOPPED" and r["rpm"] == 0) else pred["status"]

        results.append(
            MachineLatestStatus(
                machine_id=r["machine_id"],
                temperature=r["temperature"],
                vibration=r["vibration"],
                current=r["current"],
                rpm=r["rpm"],
                recorded_at=r["recorded_at"],
                status=display_status,
                risk_percent=pred["risk_percent"],
                operational_state=op_state,
            )
        )
    return results


@app.get("/api/readings/history", response_model=List[HistoryPoint], tags=["Telemetry"])
def get_history(
    machine_id: str = Query("M01", description="Machine identifier (e.g. M01, M02, M03)"),
    limit: int = Query(50, ge=1, le=200, description="Max number of points to retrieve"),
):
    """Retrieve historical telemetry for a machine in chronological order."""
    try:
        rows = db_history(machine_id, limit)
        history_points = []
        for r in rows:
            p = predict_risk(r["temperature"], r["vibration"], r["current"], r["rpm"])
            history_points.append(
                HistoryPoint(
                    temperature=r["temperature"],
                    vibration=r["vibration"],
                    current=r["current"],
                    rpm=r["rpm"],
                    risk_percent=p["risk_percent"],
                    recorded_at=r["recorded_at"],
                )
            )
        return history_points
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching historical telemetry: {str(e)}",
        )


@app.post("/api/readings", response_model=MachineLatestStatus, tags=["Telemetry"])
def create_sensor_reading(payload: SensorReadingCreate):
    """
    Ingest a new telemetry packet from a machine sensor.
    Runs ML prediction, logs reading, and triggers email alert if risk exceeds threshold.
    """
    # 1. Run ML prediction
    pred = predict_risk(
        payload.temperature,
        payload.vibration,
        payload.current,
        payload.rpm,
    )

    # 2. Persist to PostgreSQL database
    try:
        inserted = insert_reading(
            machine_id=payload.machine_id,
            temperature=payload.temperature,
            vibration=payload.vibration,
            current=payload.current,
            rpm=payload.rpm,
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

    ctrl = MACHINE_CONTROLLERS.get(payload.machine_id, {})
    op_state = ctrl.get("operational_state", "RUNNING")
    display_status = "EMERGENCY STOPPED" if (op_state == "TRIPPED_STOPPED" and payload.rpm == 0) else pred["status"]

    return MachineLatestStatus(
        machine_id=payload.machine_id,
        temperature=payload.temperature,
        vibration=payload.vibration,
        current=payload.current,
        rpm=payload.rpm,
        recorded_at=inserted["recorded_at"],
        status=display_status,
        risk_percent=pred["risk_percent"],
        operational_state=op_state,
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
        return db_recent_alerts(limit)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching alert logs: {str(e)}",
        )


@app.post("/api/alerts/test", tags=["Alerts"])
def trigger_test_alert(payload: Optional[TestEmailRequest] = None):
    """Trigger a test email notification to verify settings."""
    recipient = payload.recipient if payload else None
    result = send_test_email(recipient)
    if not result.get("sent"):
        return JSONResponse(status_code=400, content=result)
    return result


# ---------------------------------------------------------------------------
# Autonomous Telemetry Actions & Maintenance Controls
# ---------------------------------------------------------------------------
@app.post("/api/simulator/tick", tags=["Simulator"])
def simulate_cycle(payload: Optional[SimulationTickRequest] = None):
    """Manual fast-forward simulation cycle across all machines."""
    generate_autonomous_cycle()
    latest_items = get_latest_readings()
    return {"message": "Continuous telemetry cycle generated", "readings": latest_items}


@app.post("/api/simulator/normalize", tags=["Simulator"])
def normalize_machine(machine_id: str = Query(..., description="Target machine ID (e.g. M03)")):
    """
    Operator Action: Repair / Heal and restart a stopped machine back into active running state.
    """
    if machine_id not in MACHINES:
        raise HTTPException(status_code=400, detail=f"Machine {machine_id} is not in monitored list.")

    ctrl = MACHINE_CONTROLLERS.setdefault(machine_id, {})
    ctrl["operational_state"] = "RUNNING"
    ctrl["cycles"] = 0
    ctrl["cycles_to_fault"] = random.randint(6, 12)
    ctrl["temp"] = round(random.uniform(58.0, 64.0), 2)
    ctrl["vib"] = round(random.uniform(1.1, 1.6), 2)
    ctrl["curr"] = round(random.uniform(4.2, 5.2), 2)
    ctrl["rpm"] = random.randint(1600, 1720)

    reading = create_sensor_reading(
        SensorReadingCreate(
            machine_id=machine_id,
            temperature=ctrl["temp"],
            vibration=ctrl["vib"],
            current=ctrl["curr"],
            rpm=ctrl["rpm"],
        )
    )
    return {
        "message": f"Machine {machine_id} inspected, repaired, and restarted into autonomous operation.",
        "reading": reading,
    }
