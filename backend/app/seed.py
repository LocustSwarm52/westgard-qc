"""Demo data: two users, six controls, and 40 days of made-up QC results
with a few problems built in, so every rule has something to catch.

Run with:  python -m app.seed
"""
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .auth import hash_password
from .db import Base, SessionLocal, engine
from .models import Control, User
from .qc import record_run

DEMO_PASSWORD = "demo1234"

CONTROLS = [
    # instrument, analyte, level, lot, mean, sd, units
    ("Chem Analyzer 1", "Glucose", "Level 1", "GL-4471", 95.0, 2.5, "mg/dL"),
    ("Chem Analyzer 1", "Glucose", "Level 2", "GL-4472", 300.0, 6.0, "mg/dL"),
    ("Chem Analyzer 1", "Sodium", "Level 1", "NA-2210", 125.0, 1.5, "mmol/L"),
    ("Chem Analyzer 1", "Sodium", "Level 2", "NA-2211", 155.0, 1.8, "mmol/L"),
    ("Chem Analyzer 1", "Potassium", "Level 1", "K-8801", 3.5, 0.08, "mmol/L"),
    ("Chem Analyzer 1", "Potassium", "Level 2", "K-8802", 6.0, 0.12, "mmol/L"),
]


def seed(days: int = 40, rng_seed: int = 42) -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if db.scalar(select(User).limit(1)):
            print("Database already has data; skipping seed.")
            return
        sup = User(name="Dana Supervisor", email="supervisor@demo.lab",
                   password_hash=hash_password(DEMO_PASSWORD), role="supervisor")
        tech = User(name="Sam Tech", email="tech@demo.lab",
                    password_hash=hash_password(DEMO_PASSWORD), role="tech")
        db.add_all([sup, tech])
        controls = [Control(instrument=i, analyte=a, level=l, lot=lot, target_mean=m, target_sd=s, units=u)
                    for i, a, l, lot, m, s, u in CONTROLS]
        db.add_all(controls)
        db.commit()

        rng = random.Random(rng_seed)
        start = datetime.now(timezone.utc).replace(hour=7, minute=0, second=0, microsecond=0) - timedelta(days=days)
        by_analyte: dict[str, list[Control]] = {}
        for c in controls:
            by_analyte.setdefault(c.analyte, []).append(c)

        for day in range(days):
            when = start + timedelta(days=day)
            for analyte, levels in by_analyte.items():
                values = {}
                for c in levels:
                    z = rng.gauss(0, 0.8)
                    # Built-in problems:
                    if analyte == "Glucose" and 26 <= day <= 36:
                        z += 1.6                      # calibration drift: 4-1s, then 10x
                    if analyte == "Potassium" and c.level == "Level 1" and day == 12:
                        z = 3.4                       # one-off outlier: 1-3s
                    if analyte == "Sodium" and day == 18:
                        z = 2.4 if c.level == "Level 1" else -2.3   # R-4s within the run
                    if analyte == "Potassium" and day in (30, 31):
                        z = -2.3 if c.level == "Level 2" else z     # 2-2s across runs
                    values[c.id] = round(c.target_mean + z * c.target_sd, 3 if c.target_sd < 1 else 1)
                record_run(db, f"R{day + 1:03d}-{analyte[:2].upper()}", values,
                           tech, when + timedelta(minutes=len(analyte)))
        print(f"Seeded {len(controls)} controls and {days} days of results.")
        print(f"Log in as supervisor@demo.lab or tech@demo.lab, password {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
