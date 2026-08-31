"""
Simulates sensor readings for each machine and writes them to PostgreSQL
every few seconds. Mostly generates normal readings, with an occasional
abnormal spike so the dashboard has something to alert on.
"""
import random
import time

from database import ensure_schema, insert_reading
from config import MACHINES

ensure_schema()
print("Starting sensor simulation for:", ", ".join(MACHINES), "- Ctrl+C to stop.")

try:
    while True:
        for machine_id in MACHINES:
            temperature = random.uniform(50, 70)
            vibration = random.uniform(1, 2.8)
            current = random.uniform(4, 7)
            rpm = random.randint(1400, 1750)

            if random.random() < 0.15:  # ~15% chance of an abnormal reading
                temperature = random.uniform(80, 100)
                vibration = random.uniform(4, 7)
                current = random.uniform(8, 12)
                rpm = random.randint(900, 1300)

            insert_reading(machine_id, temperature, vibration, current, rpm)
            print(f"{machine_id}: T={temperature:.1f}C V={vibration:.2f} C={current:.2f}A RPM={rpm}")
        time.sleep(3)
except KeyboardInterrupt:
    print("\nSimulation stopped.")
