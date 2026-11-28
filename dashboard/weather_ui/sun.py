"""Sunrise / sunset: DB table -> live Open-Meteo -> offline astronomical calculation."""
import math
import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import requests
import streamlit as st

from .config import LAT, LON, TZ_NAME, TZ_OFFSET_H


def calc_sun(day, lat=LAT, lon=LON, tz=TZ_OFFSET_H):
    """NOAA sunrise/sunset approximation (accurate to ~1-2 min) for a date."""
    n = day.timetuple().tm_yday
    g = 2 * math.pi / 365 * (n - 1)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                       - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g)
            - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
            - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    la = math.radians(lat)
    cos_ha = (math.cos(math.radians(90.833)) / (math.cos(la) * math.cos(decl))
              - math.tan(la) * math.tan(decl))
    ha = math.degrees(math.acos(max(-1.0, min(1.0, cos_ha))))
    rise_min = (720 - 4 * (lon + ha) - eqtime + tz * 60) % 1440
    set_min = (720 - 4 * (lon - ha) - eqtime + tz * 60) % 1440
    base = datetime(day.year, day.month, day.day)
    return base + timedelta(minutes=rise_min), base + timedelta(minutes=set_min)


def _from_database(db_path, day):
    """Any table that has both a sunrise and a sunset column."""
    con = sqlite3.connect(db_path)
    try:
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for t in tables:
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{t}")')]
            sr = next((c for c in cols if "sunrise" in c.lower()), None)
            ss = next((c for c in cols if "sunset" in c.lower()), None)
            if not (sr and ss):
                continue
            df = pd.read_sql(f'SELECT "{sr}" AS sr, "{ss}" AS ss FROM "{t}"', con).dropna()
            if df.empty:
                continue
            df["sr"], df["ss"] = pd.to_datetime(df["sr"]), pd.to_datetime(df["ss"])
            row = df[df["sr"].dt.date == day]
            row = row.iloc[-1] if not row.empty else df.iloc[-1]
            base = datetime(day.year, day.month, day.day)
            return (base + timedelta(hours=row["sr"].hour, minutes=row["sr"].minute),
                    base + timedelta(hours=row["ss"].hour, minutes=row["ss"].minute))
    finally:
        con.close()
    return None


def _from_open_meteo(day):
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={"latitude": LAT, "longitude": LON, "daily": "sunrise,sunset",
                "timezone": TZ_NAME, "start_date": day.isoformat(), "end_date": day.isoformat()},
        timeout=8)
    r.raise_for_status()
    d = r.json()["daily"]
    return datetime.fromisoformat(d["sunrise"][0]), datetime.fromisoformat(d["sunset"][0])


@st.cache_data(ttl=3600)
def get_sun_times(db_path: str, day):
    """Return (sunrise, sunset, source) where source is database | Open-Meteo | calculated."""
    try:
        res = _from_database(db_path, day)
        if res:
            return (*res, "database")
    except Exception:
        pass
    try:
        return (*_from_open_meteo(day), "Open-Meteo")
    except Exception:
        pass
    return (*calc_sun(day), "calculated")
