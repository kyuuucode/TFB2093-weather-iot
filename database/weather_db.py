"""
TFB2093 IoT Project - Owner C (DB / Analytics)
Milestone 1: SQLite storage strategy (weather.db)
Milestone 2: Statistical error evaluation (MAE, RMSE, Rain confusion matrix)

Zero-cost: uses only Python stdlib sqlite3 + pandas/numpy.
Run:  python weather_db.py --demo     (builds demo_weather.db with synthetic data and prints metrics)
      python weather_db.py            (evaluates the real weather.db)

Timestamp convention (important for the whole team):
  All times are stored as ISO-8601 hourly strings, e.g. '2026-11-08T14:00'.
  Owner B must request Open-Meteo with a FIXED timezone (e.g. timezone=Asia/Kuala_Lumpur)
  for both observations and forecasts so that target_time matches obs_time exactly.
"""

import argparse
import os
import sqlite3
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# The database always lives next to this file, no matter where the script is run from
# (Icha's ingestion script, Aufa's Streamlit app and Sarah's terminal all share it).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "weather.db")
DEMO_DB_PATH = os.path.join(BASE_DIR, "demo_weather.db")

RAIN_THRESHOLD_MM = 0.1      # >= this amount counts as "rain" (observed AND forecast)
HEADLINE_LEAD_H = 24         # headline lead time used for the report
TIME_FMT = "%Y-%m-%dT%H:%M"

# ----------------------------------------------------------------------------
# MILESTONE 1 - SCHEMA
# ----------------------------------------------------------------------------
SCHEMA = """
PRAGMA foreign_keys = ON;

-- Actual observed weather, one row per location per hour
CREATE TABLE IF NOT EXISTS observations (
    obs_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    location        TEXT    NOT NULL,
    obs_time        TEXT    NOT NULL,              -- when the weather actually happened
    temperature_c   REAL,
    humidity_pct    REAL,
    wind_speed_kmh  REAL,
    precipitation_mm REAL,
    rain_observed   INTEGER GENERATED ALWAYS AS (precipitation_mm >= 0.1) VIRTUAL,
    ingested_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M','now')),
    UNIQUE (location, obs_time)
);

-- Forecast snapshots: every fetch is stored as new rows (append-only, never overwritten)
CREATE TABLE IF NOT EXISTS forecast_snapshots (
    forecast_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    location         TEXT    NOT NULL,
    issued_at        TEXT    NOT NULL,             -- when the forecast was fetched
    target_time      TEXT    NOT NULL,             -- the hour being predicted
    lead_time_hours  INTEGER NOT NULL,             -- target_time - issued_at (e.g. 24)
    temperature_c    REAL,
    humidity_pct     REAL,
    wind_speed_kmh   REAL,
    precipitation_mm REAL,
    precip_prob_pct  REAL,
    UNIQUE (location, issued_at, target_time)
);

CREATE INDEX IF NOT EXISTS idx_obs_loc_time  ON observations (location, obs_time);
CREATE INDEX IF NOT EXISTS idx_fc_target     ON forecast_snapshots (location, target_time, lead_time_hours);

-- Database-level guarantee: past forecasts can never be changed or deleted
CREATE TRIGGER IF NOT EXISTS trg_forecast_no_update
BEFORE UPDATE ON forecast_snapshots
BEGIN
    SELECT RAISE(ABORT, 'forecast_snapshots is append-only: updates are not allowed');
END;

CREATE TRIGGER IF NOT EXISTS trg_forecast_no_delete
BEFORE DELETE ON forecast_snapshots
BEGIN
    SELECT RAISE(ABORT, 'forecast_snapshots is append-only: deletes are not allowed');
END;

-- Convenience view: each forecast paired with what actually happened
CREATE VIEW IF NOT EXISTS v_forecast_vs_actual AS
SELECT  f.forecast_id, f.location, f.issued_at, f.target_time, f.lead_time_hours,
        f.temperature_c    AS fc_temp,      o.temperature_c    AS obs_temp,
        f.humidity_pct     AS fc_humidity,  o.humidity_pct     AS obs_humidity,
        f.wind_speed_kmh   AS fc_wind,      o.wind_speed_kmh   AS obs_wind,
        f.precipitation_mm AS fc_precip,    o.precipitation_mm AS obs_precip,
        f.precip_prob_pct  AS fc_precip_prob
FROM forecast_snapshots f
JOIN observations o
  ON o.location = f.location AND o.obs_time = f.target_time;
"""


def get_conn(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA)


# ----------------------------------------------------------------------------
# INSERT HELPERS (hand these to Owner B)
# ----------------------------------------------------------------------------
def insert_observation(conn, location, obs_time, temperature_c, humidity_pct,
                       wind_speed_kmh, precipitation_mm):
    """Insert one observed hour. Re-running ingestion is safe (duplicates are ignored)."""
    conn.execute(
        """INSERT OR IGNORE INTO observations
           (location, obs_time, temperature_c, humidity_pct, wind_speed_kmh, precipitation_mm)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (location, obs_time, temperature_c, humidity_pct, wind_speed_kmh, precipitation_mm),
    )


def insert_forecast_snapshot(conn, location, issued_at, target_time, temperature_c,
                             humidity_pct, wind_speed_kmh, precipitation_mm,
                             precip_prob_pct=None):
    """Insert one predicted hour as a NEW row; lead time is computed automatically."""
    lead = int(round((datetime.strptime(target_time, TIME_FMT)
                      - datetime.strptime(issued_at, TIME_FMT)).total_seconds() / 3600))
    conn.execute(
        """INSERT OR IGNORE INTO forecast_snapshots
           (location, issued_at, target_time, lead_time_hours, temperature_c,
            humidity_pct, wind_speed_kmh, precipitation_mm, precip_prob_pct)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (location, issued_at, target_time, lead, temperature_c, humidity_pct,
         wind_speed_kmh, precipitation_mm, precip_prob_pct),
    )


# ----------------------------------------------------------------------------
# MILESTONE 2 - EVALUATION ENGINE
# ----------------------------------------------------------------------------
VARIABLES = {
    "Temperature (°C)":  ("fc_temp",     "obs_temp"),
    "Humidity (%)":      ("fc_humidity", "obs_humidity"),
    "Wind Speed (km/h)": ("fc_wind",     "obs_wind"),
}


def load_pairs(db_path: str = DB_PATH, location: str | None = None) -> pd.DataFrame:
    """Every forecast paired with the observation for its target hour."""
    with get_conn(db_path) as conn:
        q = "SELECT * FROM v_forecast_vs_actual"
        params = ()
        if location:
            q += " WHERE location = ?"
            params = (location,)
        return pd.read_sql_query(q, conn, params=params)


def mae(pred, obs) -> float:
    return float(np.mean(np.abs(pred - obs)))


def rmse(pred, obs) -> float:
    return float(np.sqrt(np.mean((pred - obs) ** 2)))


def error_metrics(df: pd.DataFrame, by_lead_time: bool = False) -> pd.DataFrame:
    """MAE and RMSE for temperature, humidity and wind speed (optionally per lead time)."""
    groups = df.groupby("lead_time_hours") if by_lead_time else [("All", df)]
    rows = []
    for lead, g in groups:
        for name, (fc, ob) in VARIABLES.items():
            pair = g[[fc, ob]].dropna()
            if pair.empty:
                continue
            row = {"Variable": name, "n": len(pair),
                   "MAE": round(mae(pair[fc], pair[ob]), 3),
                   "RMSE": round(rmse(pair[fc], pair[ob]), 3)}
            if by_lead_time:
                row = {"Lead (h)": int(lead), **row}
            rows.append(row)
    return pd.DataFrame(rows)


def rain_confusion_matrix(df: pd.DataFrame, threshold_mm: float = RAIN_THRESHOLD_MM,
                          prob_threshold: float | None = None) -> dict:
    """
    2x2 rain confusion matrix.
      Observed rain  = obs_precip >= threshold_mm
      Predicted rain = fc_precip  >= threshold_mm   (or fc_precip_prob >= prob_threshold if given)
    """
    d = df.dropna(subset=["fc_precip", "obs_precip"])
    actual = d["obs_precip"] >= threshold_mm
    if prob_threshold is not None:
        predicted = d["fc_precip_prob"] >= prob_threshold
    else:
        predicted = d["fc_precip"] >= threshold_mm

    tp = int((predicted & actual).sum())      # predicted rain, rain happened
    fp = int((predicted & ~actual).sum())     # False Alarm
    tn = int((~predicted & ~actual).sum())    # predicted dry, stayed dry
    fn = int((~predicted & actual).sum())     # Miss
    total = tp + fp + tn + fn

    def safe(a, b):
        return round(a / b, 3) if b else None

    return {
        "TP": tp, "FP (False Alarm)": fp, "TN": tn, "FN (Miss)": fn, "Total": total,
        "Accuracy": safe(tp + tn, total),
        "Precision": safe(tp, tp + fp),
        "Recall (POD)": safe(tp, tp + fn),
        "False Alarm Ratio": safe(fp, tp + fp),
    }


def confusion_matrix_df(cm: dict) -> pd.DataFrame:
    """2x2 DataFrame version of the confusion matrix (handy for Streamlit)."""
    return pd.DataFrame(
        [[cm["TP"], cm["FP (False Alarm)"]], [cm["FN (Miss)"], cm["TN"]]],
        index=["Predicted RAIN", "Predicted DRY"],
        columns=["Observed RAIN", "Observed DRY"],
    )


def print_confusion_matrix(cm: dict, title: str = "Rain Confusion Matrix") -> None:
    print(f"\n{title}")
    print("                    Observed RAIN   Observed DRY")
    print(f"Predicted RAIN      {cm['TP']:^13}   {cm['FP (False Alarm)']:^12}   (TP | False Alarm)")
    print(f"Predicted DRY       {cm['FN (Miss)']:^13}   {cm['TN']:^12}   (Miss | TN)")
    print(f"\nAccuracy={cm['Accuracy']}  Precision={cm['Precision']}  "
          f"Recall={cm['Recall (POD)']}  FAR={cm['False Alarm Ratio']}")


def run_evaluation(db_path: str = DB_PATH, location: str | None = None) -> None:
    df = load_pairs(db_path, location)
    if df.empty:
        print("No matched forecast/observation pairs yet - keep the ingestion running.")
        return
    leads = sorted(int(x) for x in df["lead_time_hours"].unique())
    print(f"Matched pairs: {len(df)}  |  Lead times (h): {leads}")
    print("\nOverall error metrics (all lead times combined)")
    print(error_metrics(df).to_string(index=False))
    print("\nError metrics by lead time")
    print(error_metrics(df, by_lead_time=True).to_string(index=False))
    print_confusion_matrix(rain_confusion_matrix(df), "Rain Confusion Matrix (all lead times)")

    headline = df[df["lead_time_hours"] == HEADLINE_LEAD_H]
    if headline.empty:
        print(f"\nNo {HEADLINE_LEAD_H}h forecasts yet for the headline results.")
    else:
        print_confusion_matrix(rain_confusion_matrix(headline),
                               f"Rain Confusion Matrix ({HEADLINE_LEAD_H}h headline)")


# ----------------------------------------------------------------------------
# DEMO DATA (3 days continuous, hourly) - lets you test everything before Owner B's data arrives
# ----------------------------------------------------------------------------
def build_demo(db_path: str = DEMO_DB_PATH, location: str = "Seri Iskandar") -> None:
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db(db_path)
    rng = np.random.default_rng(42)
    start = datetime(2026, 11, 5, 0, 0)
    hours = 72
    truth = {}
    with get_conn(db_path) as conn:
        for h in range(hours):
            t = start + timedelta(hours=h)
            temp = 27 + 5 * np.sin((t.hour - 9) / 24 * 2 * np.pi) + rng.normal(0, 0.5)
            hum = 80 - 2.5 * (temp - 27) + rng.normal(0, 3)
            wind = max(0, 8 + rng.normal(0, 2))
            rain = float(rng.random() < 0.2) * rng.uniform(0.2, 4)
            truth[t] = (temp, hum, wind, rain)
            insert_observation(conn, location, t.strftime(TIME_FMT), temp, hum, wind, rain)
        # forecasts issued at 24h, 12h and 6h before each target hour
        for t, (temp, hum, wind, rain) in truth.items():
            for lead in (24, 12, 6):
                issued = (t - timedelta(hours=lead)).strftime(TIME_FMT)
                s = lead / 12
                f_rain = rain if rng.random() > 0.15 * s else 0.0
                if rain == 0 and rng.random() < 0.05 * s:
                    f_rain = rng.uniform(0.2, 2)
                insert_forecast_snapshot(
                    conn, location, issued, t.strftime(TIME_FMT),
                    temp + rng.normal(0, 0.6 * s), hum + rng.normal(0, 3 * s),
                    max(0, wind + rng.normal(0, 1.5 * s)), f_rain,
                    min(100, 90 if f_rain > 0 else 10))
    print(f"Demo database built: {db_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="build and evaluate synthetic demo data")
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--location", default=None)
    args = ap.parse_args()

    if args.demo:
        build_demo(DEMO_DB_PATH)
        run_evaluation(DEMO_DB_PATH)
    else:
        init_db(args.db)
        run_evaluation(args.db, args.location)