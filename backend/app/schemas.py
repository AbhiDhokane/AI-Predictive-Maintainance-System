"""
Pydantic Schemas for AI Predictive Maintenance REST API.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field


class SensorReadingCreate(BaseModel):
    machine_id: str = Field(..., example="M01", description="Machine identifier (e.g. M01, M02)")
    temperature: float = Field(..., example=65.4, description="Temperature in Celsius")
    vibration: float = Field(..., example=2.15, description="Vibration in mm/s")
    current: float = Field(..., example=5.8, description="Current in Amperes")
    rpm: int = Field(..., example=1650, description="Rotational speed in RPM")


class SensorReadingResponse(BaseModel):
    id: Optional[int] = None
    machine_id: str
    temperature: float
    vibration: float
    current: float
    rpm: int
    recorded_at: Union[datetime, str]


class MachineLatestStatus(BaseModel):
    machine_id: str
    temperature: float
    vibration: float
    current: float
    rpm: int
    recorded_at: Union[datetime, str]
    status: str  # NORMAL, WARNING, HIGH FAILURE RISK, EMERGENCY STOPPED
    risk_percent: float
    operational_state: Optional[str] = "RUNNING"  # "RUNNING" or "TRIPPED_STOPPED"
    alert_info: Optional[Dict[str, Any]] = None


class HistoryPoint(BaseModel):
    temperature: float
    vibration: float
    current: float
    rpm: int
    recorded_at: Union[datetime, str]


class PredictionRequest(BaseModel):
    temperature: float = Field(..., example=85.2)
    vibration: float = Field(..., example=5.6)
    current: float = Field(..., example=9.8)
    rpm: int = Field(..., example=1100)


class PredictionResponse(BaseModel):
    predicted_class: int
    status: str
    risk_percent: float
    probabilities: List[float]


class AlertLogItem(BaseModel):
    id: int
    machine_id: str
    risk_percent: float
    status: str
    recipients: List[str]
    email_status: str
    error_message: Optional[str] = None
    sent_at: Union[datetime, str]


class SystemOverview(BaseModel):
    total_readings: int
    total_alerts_sent: int
    monitored_machines: List[str]
    alert_threshold: int
    email_alerts_enabled: bool
    machines: List[MachineLatestStatus]


class TestEmailRequest(BaseModel):
    recipient: Optional[str] = Field(None, example="engineer@example.com")


class SimulationTickRequest(BaseModel):
    abnormal_chance: Optional[float] = Field(0.15, ge=0.0, le=1.0, description="Probability of generating an abnormal anomaly reading")
