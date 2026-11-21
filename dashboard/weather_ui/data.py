"""Data layer: live DB sync from GitHub + loading tables into DataFrames.

Evaluation logic (MAE, RMSE, confusion matrix) lives in Owner C's module
`database/weather_db.py`, imported here as `wdb`.
"""
import os
import sqlite3
import sys
import tempfile

import pandas as pd
import requests
import streamlit as st

from .config import REPO_DB_URL

# link to Owner C's module (<repo>/database/weather_db.py)
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "database"))
import weather_db as wdb  # noqa: E402


@st.cache_data(ttl=120, show_spinner=False)
def get_fresh_db():
    """Download the newest weather.db committed by the hourly cronjob.

    Cached for 2 min so changing a widget / theme doesn't re-download it every time.
    """
    try:
        r = requests.get(REPO_DB_URL, timeout=15)
        r.raise_for_status()
        path = os.path.join(tempfile.gettempdir(), "weather_live.db")
        with open(path, "wb") as f:
            f.write(r.content)
        return path
    except Exception:
        return None


def resolve_db_path():
    """Return (db_path, using_demo). Order: fresh GitHub copy -> $WEATHER_DB / bundled -> demo."""
    path = get_fresh_db() or os.environ.get("WEATHER_DB", wdb.DB_PATH)
    if os.path.exists(path):
        return path, False
    if not os.path.exists(wdb.DEMO_DB_PATH):
        wdb.build_demo(wdb.DEMO_DB_PATH)
    return wdb.DEMO_DB_PATH, True


@st.cache_data(ttl=60)
def load(db_path: str):
    """Return (observations, forecast snapshots, matched forecast/observation pairs)."""
    con = sqlite3.connect(db_path)
    obs = pd.read_sql(
        "SELECT location, obs_time, temperature_c, humidity_pct, rainfall_mm, wind_speed_kmh "
        "FROM observations", con)
    fc = pd.read_sql(
        "SELECT location, issued_at, target_time, lead_time_hours, temperature_c, humidity_pct, "
        "rainfall_mm, wind_speed_kmh, rain_probability_pct FROM forecast_snapshots", con)
    con.close()
    pairs = wdb.load_pairs(db_path)
    obs["obs_time"] = pd.to_datetime(obs["obs_time"])
    fc["target_time"] = pd.to_datetime(fc["target_time"])
    fc["issued_at"] = pd.to_datetime(fc["issued_at"])
    pairs["target_time"] = pd.to_datetime(pairs["target_time"])
    return (obs.sort_values("obs_time"), fc.sort_values("target_time"),
            pairs.sort_values("target_time"))
