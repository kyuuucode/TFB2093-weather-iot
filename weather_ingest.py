"""
TFB2093 IoT Project - Owner B: Open-Meteo ingestion script
Location : Seri Iskandar, Perak (4.3582, 100.9782)
Metrics  : Temperature, Humidity, Rainfall, Wind Speed, Forecasts
           (forecast = hourly values for future hours + rain probability)

Install  : pip install requests schedule
Run      : python weather_ingest.py          (keep it running >= 3 days)
           python weather_ingest.py --once   (single fetch, for testing)

Outputs (all in ./data/, zero-cost CSV so Owner C can load into SQLite):
  readings_log.csv          - 'current' reading, appended every run (proof of continuous monitoring)
  hourly_observations.csv   - hourly values for past hours (de-duplicated by timestamp)
  forecast_snapshots.csv    - forecast hours, appended every run with fetched_at
                              (lets Owner C compare forecast vs actual -> MAE/RMSE)
"""

import csv
import logging
import os
import sys
import time
from datetime import datetime

import requests
import schedule

# ---------------- Configuration ----------------
LATITUDE = 4.3582
LONGITUDE = 100.9782
API_URL = "https://api.open-meteo.com/v1/forecast"
TIMEZONE = "Asia/Kuala_Lumpur"
PAST_DAYS = 3          # Milestone 2: pull historical data immediately
FORECAST_DAYS = 3
RUN_EVERY_MINUTES = 60  # hourly is enough; Open-Meteo data is hourly
DATA_DIR = "data"

HOURLY_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
    "precipitation_probability",
]
CURRENT_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
]

FIELDS = ["time", "temperature_c", "humidity_pct", "rainfall_mm",
          "wind_speed_kmh", "rain_probability_pct"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("ingest.log"), logging.StreamHandler()],
)
log = logging.getLogger("ingest")


# ---------------- API call ----------------
def fetch_weather(retries=3, backoff=10):
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "current": ",".join(CURRENT_VARS),
        "hourly": ",".join(HOURLY_VARS),
        "past_days": PAST_DAYS,
        "forecast_days": FORECAST_DAYS,
        "timezone": TIMEZONE,
    }
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(API_URL, params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            log.warning("Attempt %d/%d failed: %s", attempt, retries, e)
            time.sleep(backoff * attempt)
    raise RuntimeError("Open-Meteo request failed after retries")


# ---------------- CSV helpers ----------------
def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def append_rows(filename, header, rows):
    _ensure_dir()
    path = os.path.join(DATA_DIR, filename)
    new_file = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(header)
        w.writerows(rows)


def upsert_rows(filename, header, rows, key_index=0):
    """Rewrite file, keeping one row per timestamp (latest value wins)."""
    _ensure_dir()
    path = os.path.join(DATA_DIR, filename)
    existing = {}
    if os.path.exists(path):
        with open(path, newline="") as f:
            for row in csv.reader(f):
                if row and row[key_index] != header[key_index]:
                    existing[row[key_index]] = row
    for row in rows:
        existing[str(row[key_index])] = [str(x) for x in row]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for k in sorted(existing):
            w.writerow(existing[k])


# ---------------- Main job ----------------
def run_job():
    fetched_at = datetime.now().isoformat(timespec="seconds")
    log.info("Fetching Open-Meteo data...")
    data = fetch_weather()

    # 1) Current reading (appended every run)
    cur = data["current"]
    append_rows(
        "readings_log.csv",
        ["fetched_at"] + FIELDS[:-1],
        [[fetched_at, cur["time"], cur["temperature_2m"],
          cur["relative_humidity_2m"], cur["precipitation"],
          cur["wind_speed_10m"]]],
    )

    # 2) Split hourly arrays into past (observations) vs future (forecast)
    h = data["hourly"]
    now_hour = cur["time"][:13]  # 'YYYY-MM-DDTHH'
    past_rows, future_rows = [], []
    for i, t in enumerate(h["time"]):
        row = [t, h["temperature_2m"][i], h["relative_humidity_2m"][i],
               h["precipitation"][i], h["wind_speed_10m"][i],
               h["precipitation_probability"][i]]
        (past_rows if t[:13] <= now_hour else future_rows).append(row)

    upsert_rows("hourly_observations.csv", FIELDS, past_rows)
    append_rows(
        "forecast_snapshots.csv",
        ["fetched_at"] + FIELDS,
        [[fetched_at] + r for r in future_rows],
    )

    log.info("Saved: 1 current, %d past hours, %d forecast hours | "
             "now: %.1f C, %s%% RH, %.1f mm, %.1f km/h",
             len(past_rows), len(future_rows), cur["temperature_2m"],
             cur["relative_humidity_2m"], cur["precipitation"],
             cur["wind_speed_10m"])


def safe_job():
    try:
        run_job()
    except Exception:
        log.exception("Job failed; will retry on next schedule")


if __name__ == "__main__":
    safe_job()  # run immediately -> past_days history is stored at once
    if "--once" in sys.argv:
        sys.exit(0)
    schedule.every(RUN_EVERY_MINUTES).minutes.do(safe_job)
    log.info("Scheduler started: every %d min. Ctrl+C to stop.", RUN_EVERY_MINUTES)
    while True:
        schedule.run_pending()
        time.sleep(30)
