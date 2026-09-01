"""
Machine Learning inference service for AI Predictive Maintenance.
Loads the trained Random Forest model and performs real-time failure risk classification.
"""
import os
import joblib
import pandas as pd
from typing import Dict, Any, Tuple

# Try loading from multiple standard paths
_MODEL_PATHS = [
    os.path.join(os.path.dirname(__file__), "..", "model", "failure_model.pkl"),
    os.path.join(os.path.dirname(__file__), "..", "..", "model", "failure_model.pkl"),
    "model/failure_model.pkl",
]

_model = None

STATUS_LABELS = ["NORMAL", "WARNING", "HIGH FAILURE RISK"]


def get_model():
    """Load and cache the scikit-learn failure prediction model."""
    global _model
    if _model is not None:
        return _model

    for path in _MODEL_PATHS:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            try:
                _model = joblib.load(abs_path)
                return _model
            except Exception as e:
                print(f"Warning: Failed to load model from {abs_path}: {e}")

    raise FileNotFoundError(
        f"Predictive maintenance model failure_model.pkl not found in expected paths: {_MODEL_PATHS}. "
        f"Please run train_model.py first."
    )


def predict_risk(temperature: float, vibration: float, current: float, rpm: int) -> Dict[str, Any]:
    """
    Given 4 sensor telemetry features:
      - temperature (°C)
      - vibration (mm/s)
      - current (A)
      - rpm (RPM)
    
    Returns:
      {
        "predicted_class": 0, 1, or 2,
        "status": "NORMAL" | "WARNING" | "HIGH FAILURE RISK",
        "risk_percent": float (0-100),
        "probabilities": [prob_normal, prob_warning, prob_high_risk]
      }
    """
    model = get_model()
    features = pd.DataFrame(
        [[temperature, vibration, current, rpm]],
        columns=["temperature", "vibration", "current", "rpm"]
    )
    predicted_class = int(model.predict(features)[0])
    probabilities = model.predict_proba(features)[0]
    
    # Class 2 corresponds to HIGH FAILURE RISK
    risk_percent = float(probabilities[2] * 100.0) if len(probabilities) > 2 else 0.0
    status = STATUS_LABELS[predicted_class] if 0 <= predicted_class < len(STATUS_LABELS) else "UNKNOWN"

    return {
        "predicted_class": predicted_class,
        "status": status,
        "risk_percent": round(risk_percent, 2),
        "probabilities": [round(float(p), 4) for p in probabilities],
    }
