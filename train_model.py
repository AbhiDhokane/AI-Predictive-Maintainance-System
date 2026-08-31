"""
Trains a RandomForest classifier on synthetic sensor data and saves it
to model/failure_model.pkl. Run this once before starting the app.
"""
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier

np.random.seed(42)

rows = []
for _ in range(4000):
    temperature = np.random.uniform(45, 100)
    vibration = np.random.uniform(0.8, 7)
    current = np.random.uniform(3, 12)
    rpm = np.random.uniform(900, 1800)

    bad_signals = sum([
        temperature > 80,
        vibration > 4,
        current > 8,
        rpm < 1300,
    ])
    # 0 = normal, 1 = warning, 2 = high failure risk
    status = 2 if bad_signals >= 3 else (1 if bad_signals >= 1 else 0)
    rows.append([temperature, vibration, current, rpm, status])

data = pd.DataFrame(rows, columns=["temperature", "vibration", "current", "rpm", "status"])

model = RandomForestClassifier(n_estimators=150, random_state=42, class_weight="balanced")
model.fit(data.iloc[:, :4], data.status)

joblib.dump(model, "model/failure_model.pkl")
print("Model saved to model/failure_model.pkl")
