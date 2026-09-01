"""
Simulates sensor telemetry readings for each monitored machine and writes them to PostgreSQL.
Can be run locally as a background generator, or as a background worker process.
"""
import random
import time
from app.config import MACHINES
from app.database import ensure_schema, insert_reading

if __name__ == "__main__":
    ensure_schema()
    print("Starting sensor simulation for:", ", ".join(MACHINES), "- Press Ctrl+C to stop.")

    try:
        while True:
            for machine_id in MACHINES:
                temperature = random.uniform(50, 70)
                vibration = random.uniform(1, 2.8)
                current = random.uniform(4, 7)
                rpm = random.randint(1400, 1750)

                # ~15% chance of abnormal reading
                if random.random() < 0.15:
                    temperature = random.uniform(80, 100)
                    vibration = random.uniform(4, 7)
                    current = random.uniform(8, 12)
                    rpm = random.randint(900, 1300)

                insert_reading(
                    machine_id,
                    round(temperature, 2),
                    round(vibration, 2),
                    round(current, 2),
                    rpm,
                )
                print(f"[{machine_id}] Temp: {temperature:.1f}°C | Vib: {vibration:.2f} mm/s | Cur: {current:.2f}A | RPM: {rpm}")
            time.sleep(3)
    except KeyboardInterrupt:
        print("\nSimulation stopped.")
