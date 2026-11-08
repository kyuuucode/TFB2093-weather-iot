"""Creates a demo SQLite DB with the assumed schema (replace with Owner C's real weather.db)."""
import sqlite3
import numpy as np
import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,          -- ISO8601 local time, e.g. 2026-11-05 14:00:00
  temperature REAL, humidity REAL, rainfall REAL, wind_speed REAL);
CREATE TABLE IF NOT EXISTS forecasts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fetched_at TEXT NOT NULL,         -- when the forecast was retrieved
  target_time TEXT NOT NULL,        -- time the forecast is predicting
  horizon_hours INTEGER NOT NULL,   -- target_time - fetched_at
  temperature REAL, humidity REAL, rainfall REAL, wind_speed REAL);
"""

def build_demo_db(path="weather.db", days=4, seed=7):
    rng = np.random.default_rng(seed)
    end = pd.Timestamp.now().floor("h")
    times = pd.date_range(end - pd.Timedelta(days=days), end, freq="h")
    h = times.hour.values
    temp = 27.5 + 4.5 * np.sin((h - 9) / 24 * 2 * np.pi) + rng.normal(0, .5, len(h))
    hum = np.clip(82 - 3.2 * (temp - 27.5) + rng.normal(0, 3, len(h)), 40, 100)
    rain = np.where((h >= 14) & (h <= 19) & (rng.random(len(h)) < .5), rng.gamma(2, 2, len(h)), 0.0)
    wind = np.clip(6 + 2 * np.sin(h / 24 * 2 * np.pi) + rng.normal(0, 1.2, len(h)), 0, None)
    obs = pd.DataFrame(dict(timestamp=times.strftime("%Y-%m-%d %H:%M:%S"),
                            temperature=temp, humidity=hum, rainfall=rain, wind_speed=wind))
    rows = []
    for hz in (1, 3, 6, 12, 24):
        s = .4 + .08 * hz
        f = pd.DataFrame(dict(
            fetched_at=(times - pd.Timedelta(hours=hz)).strftime("%Y-%m-%d %H:%M:%S"),
            target_time=obs.timestamp, horizon_hours=hz,
            temperature=temp + rng.normal(0, s, len(h)),
            humidity=np.clip(hum + rng.normal(0, 2 * s + 1, len(h)), 0, 100),
            rainfall=np.clip(rain * rng.uniform(.3, 1.4, len(h)) + rng.normal(0, .3 * s, len(h)), 0, None) *
                     (rng.random(len(h)) > .15 + .01 * hz),
            wind_speed=np.clip(wind + rng.normal(0, s, len(h)), 0, None)))
        rows.append(f)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.execute("DELETE FROM observations"); con.execute("DELETE FROM forecasts")
    obs.to_sql("observations", con, if_exists="append", index=False)
    pd.concat(rows).to_sql("forecasts", con, if_exists="append", index=False)
    con.commit(); con.close()

if __name__ == "__main__":
    build_demo_db(); print("weather.db created")
