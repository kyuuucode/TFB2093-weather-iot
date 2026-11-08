"""Quick health check of a weather database.

Usage:
    python check_db.py                    (checks weather.db next to this file)
    python check_db.py demo_weather.db    (checks another database)
"""
import os
import sqlite3
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, "weather.db")

if not os.path.exists(db):
    sys.exit(f"Database not found: {db}")

with sqlite3.connect(db) as conn:
    c = conn.cursor()
    print(f"Database: {db}\n")
    for table in ("observations", "forecast_snapshots"):
        n = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {n} rows")
    print("\nObservation range:",
          c.execute("SELECT MIN(obs_time), MAX(obs_time) FROM observations").fetchone())
    print("Forecast target range:",
          c.execute("SELECT MIN(target_time), MAX(target_time) FROM forecast_snapshots").fetchone())
    print("Matched forecast/observation pairs:",
          c.execute("SELECT COUNT(*) FROM v_forecast_vs_actual").fetchone()[0])
    print("\nRows per lead time:")
    for lead, n in c.execute("SELECT lead_time_hours, COUNT(*) FROM forecast_snapshots "
                             "GROUP BY 1 ORDER BY 1"):
        print(f"  {lead}h: {n}")