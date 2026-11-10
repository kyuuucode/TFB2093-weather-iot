"""Seri Iskandar Weather Monitor - Streamlit dashboard (TFB2093 IoT Project, Owner: Aufa).

Reads Owner C's SQLite database (database/weather.db) and uses Owner C's evaluation
engine (database/weather_db.py) for MAE, RMSE and the rain confusion matrix.

LIVE SYNC: the dashboard downloads the latest weather.db committed by the hourly
cronjob from GitHub, so the deployed app always shows fresh data without waiting
for a Streamlit Cloud redeploy. Falls back to the bundled DB if offline.

Run from the repo root:   streamlit run dashboard/app.py
"""
import os
import sqlite3
import sys
import tempfile

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ---------- link to Owner C's module ----------
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "database"))
import weather_db as wdb  # noqa: E402  (Owner C: schema, load_pairs, error_metrics, rain_confusion_matrix)

DB_PATH = os.environ.get("WEATHER_DB", wdb.DB_PATH)

# ---------- live database sync (new) ----------
REPO_DB_URL = "https://raw.githubusercontent.com/kyuuucode/TFB2093-weather-iot/main/database/weather.db"


def get_fresh_db():
    """Download the newest weather.db snapshot committed by the hourly cronjob."""
    try:
        r = requests.get(REPO_DB_URL, timeout=15)
        r.raise_for_status()
        path = os.path.join(tempfile.gettempdir(), "weather_live.db")
        with open(path, "wb") as f:
            f.write(r.content)
        return path
    except Exception:
        return None  # offline -> fall back to the bundled DB


_fresh = get_fresh_db()
if _fresh:
    DB_PATH = _fresh

# auto-refresh the page every 5 minutes so new hourly data appears on its own
st.markdown('<meta http-equiv="refresh" content="300">', unsafe_allow_html=True)

# display name -> (observations column, unit, colour, forecast col in view, observed col in view)
PARAMS = {
    "Temperature": ("temperature_c", "°C", "#ef553b", "fc_temp", "obs_temp"),
    "Humidity": ("humidity_pct", "%", "#00cc96", "fc_humidity", "obs_humidity"),
    "Rainfall": ("rainfall_mm", "mm", "#636efa", "fc_rain", "obs_rain"),
    "Wind speed": ("wind_speed_kmh", "km/h", "#ab63fa", "fc_wind", "obs_wind"),
}

st.set_page_config(page_title="Seri Iskandar Weather", page_icon="🌦️", layout="wide")

# CSS Baharu: Bento Grid & Glassmorphism (Sokong Light/Night Mode)
st.markdown(
    """<style>
    /* Styling untuk kad metrik */
    div[data-testid="stMetric"] {
        background-color: var(--secondary-background-color);
        border: 1px solid rgba(150, 150, 150, 0.15);
        border-radius: 20px;
        padding: 20px;
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.08);
        transition: transform 0.2s ease-in-out, box-shadow 0.2s ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 20px rgba(0, 0, 0, 0.12);
    }
    /* Membesarkan saiz nilai metrik utama (Suhu, dll) */
    div[data-testid="stMetricValue"] {
        font-size: 2.2rem !important;
        font-weight: 700 !important;
    }
    /* Kotak Info (Next forecast) */
    div.stAlert {
        border-radius: 16px;
        border: none;
    }
    .block-container {
        padding-top: 2rem;
        max-width: 1200px; /* Hadkan lebar supaya tak nampak kosong */
    }
    </style>""", unsafe_allow_html=True)

# ---------- data layer ----------
using_demo = False
if not os.path.exists(DB_PATH):
    if not os.path.exists(wdb.DEMO_DB_PATH):
        wdb.build_demo(wdb.DEMO_DB_PATH)
    DB_PATH = wdb.DEMO_DB_PATH
    using_demo = True


@st.cache_data(ttl=60)
def load(db_path: str):
    con = sqlite3.connect(db_path)
    obs = pd.read_sql(
        "SELECT location, obs_time, temperature_c, humidity_pct, rainfall_mm, wind_speed_kmh "
        "FROM observations", con)
    fc = pd.read_sql(
        "SELECT location, issued_at, target_time, lead_time_hours, temperature_c, humidity_pct, "
        "rainfall_mm, wind_speed_kmh, rain_probability_pct FROM forecast_snapshots", con)
    con.close()
    pairs = wdb.load_pairs(db_path)  # Owner C's v_forecast_vs_actual view
    obs["obs_time"] = pd.to_datetime(obs["obs_time"])
    fc["target_time"] = pd.to_datetime(fc["target_time"])
    fc["issued_at"] = pd.to_datetime(fc["issued_at"])
    pairs["target_time"] = pd.to_datetime(pairs["target_time"])
    return (obs.sort_values("obs_time"), fc.sort_values("target_time"),
            pairs.sort_values("target_time"))


def fmt(x, d=2):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    return f"{x:.{d}f}"


obs_all, fc_all, pairs_all = load(DB_PATH)

# ---------- sidebar ----------
with st.sidebar:
    st.title("🌦️ Controls")
    if obs_all.empty:
        st.error("No observations in database yet. Keep the ingestion script running.")
        st.stop()

    locations = sorted(obs_all["location"].unique())
    loc = st.selectbox("Location", locations) if len(locations) > 1 else locations[0]
    obs = obs_all[obs_all["location"] == loc]
    fc = fc_all[fc_all["location"] == loc]
    pairs = pairs_all[pairs_all["location"] == loc]

    dmin, dmax = obs["obs_time"].min().date(), obs["obs_time"].max().date()
    rng = st.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)
    if isinstance(rng, tuple) and len(rng) == 2:
        d0, d1 = rng
    else:
        d0 = d1 = rng[0] if isinstance(rng, tuple) else rng

    horizons = sorted(int(x) for x in pairs["lead_time_hours"].unique()) if not pairs.empty else []
    if horizons:
        default = horizons.index(wdb.HEADLINE_LEAD_H) if wdb.HEADLINE_LEAD_H in horizons else len(horizons) - 1
        hz = st.selectbox("Forecast lead time (hours ahead)", horizons, index=default)
    else:
        hz = None
    rain_thr = st.slider("Rain threshold (mm/h)", 0.1, 2.0, float(wdb.RAIN_THRESHOLD_MM), 0.1,
                         help="An hour counts as 'rain' if rainfall ≥ this value.")
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Location: {loc}, Perak (4.37°N, 100.97°E)\n\nDB: `{os.path.basename(DB_PATH)}`")

obs_f = obs[(obs["obs_time"].dt.date >= d0) & (obs["obs_time"].dt.date <= d1)]
pairs_f = pairs[(pairs["target_time"].dt.date >= d0) & (pairs["target_time"].dt.date <= d1)]
pairs_hz = pairs_f[pairs_f["lead_time_hours"] == hz].sort_values("target_time") if hz is not None else pairs_f.iloc[0:0]

# ---------- header ----------
st.title("🌦️ Seri Iskandar Weather Monitor")
st.caption("Open-Meteo observations vs. forecasts · TFB2093 Internet-of-Things")
if using_demo:
    st.warning("database/weather.db not found – showing **demo data** from Owner C's demo builder.")

t1, t2, t3, t4 = st.tabs(["📍 Current", "📈 Actual vs Forecast", "🎯 Accuracy", "💾 Data & Export"])

# ---------- Tab 1: current summary ----------
with t1:
    last = obs.iloc[-1]
    prev = obs.iloc[-2] if len(obs) > 1 else last
    st.subheader(f"📍 Latest reading · {last['obs_time']:%d %b %Y, %H:%M}")
    
    def delta(col, d=1):
        if pd.isna(last[col]) or pd.isna(prev[col]):
            return None
        return f"{last[col] - prev[col]:+.{d}f}"

    # SUSUNAN BENTO GRID: Kiri (Besar), Kanan (Grid 2x2)
    col_main, col_metrics = st.columns([1.2, 2], gap="large")

    with col_main:
        # Kad Utama: Suhu
        st.metric("🌡️ Temperature", f"{fmt(last.temperature_c, 1)} °C", delta("temperature_c"))
        
        # Ramalan seterusnya diselitkan di bawah suhu (macam widget kiri dalam gambar)
        nxt = (fc[fc["target_time"] > last["obs_time"]]
               .sort_values(["target_time", "lead_time_hours"])
               .drop_duplicates("target_time"))
        if not nxt.empty:
            n = nxt.iloc[0]
            prob = f" ({n.rain_probability_pct:.0f}% rain)" if pd.notna(n.rain_probability_pct) else ""
            st.info(f"**Forecast ({n['target_time']:%H:%M}):**\n\n"
                    f"🌡️ {fmt(n.temperature_c, 1)}°C | 🌧️ {fmt(n.rainfall_mm, 1)}mm {prob}\n\n"
                    f"💨 {fmt(n.wind_speed_kmh, 1)}km/h | 💧 {fmt(n.humidity_pct, 0)}%")
            rain_soon = nxt.head(6)["rainfall_mm"].max()
            if pd.notna(rain_soon) and rain_soon >= rain_thr:
                st.warning("☔ Rain expected within the next 6 hours.")

    with col_metrics:
        # Baris Atas Grid
        m1, m2 = st.columns(2)
        m1.metric("💨 Wind speed", f"{fmt(last.wind_speed_kmh, 1)} km/h", delta("wind_speed_kmh"))
        m2.metric("🌧️ Rainfall", f"{fmt(last.rainfall_mm, 1)} mm", delta("rainfall_mm"), delta_color="inverse")
        
        # Baris Bawah Grid
        m3, m4 = st.columns(2)
        m3.metric("💧 Humidity", f"{fmt(last.humidity_pct, 0)} %", delta("humidity_pct", 0))
        
        # Tambahan Modern: Graf Gauge untuk Kelembapan (Meniru UV Index dari gambar)
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=last.humidity_pct,
            number={'suffix': "%", 'font': {'size': 24}},
            title={'text': "Humidity Level", 'font': {'size': 14}},
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "gray"},
                'bar': {'color': PARAMS["Humidity"][2]},
                'bgcolor': "rgba(0,0,0,0)",
                'borderwidth': 0,
                'steps': [
                    {'range': [0, 40], 'color': "rgba(239, 85, 59, 0.15)"},
                    {'range': [40, 70], 'color': "rgba(0, 204, 150, 0.15)"},
                    {'range': [70, 100], 'color': "rgba(99, 110, 250, 0.15)"}],
            }
        ))
        fig_gauge.update_layout(height=160, margin=dict(l=10, r=10, t=30, b=0), 
                                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                font={'color': "var(--text-color)"})
        m4.plotly_chart(fig_gauge, use_container_width=True)

    st.markdown("---")
    st.subheader("Last 24 h Trend")
    day = obs[obs["obs_time"] >= obs["obs_time"].max() - pd.Timedelta(hours=24)]
    fig = go.Figure()
    for nme in ("Temperature", "Humidity"):
        col, u, clr, _, _ = PARAMS[nme]
        fig.add_scatter(x=day.obs_time, y=day[col], name=f"{nme} ({u})", line=dict(color=clr, shape='spline', smoothing=1.3))
    fig.add_bar(x=day.obs_time, y=day.rainfall_mm, name="Rainfall (mm)",
                marker_color=PARAMS["Rainfall"][2], opacity=.5)
    
    fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0), hovermode="x unified",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True)

# ---------- Tab 2: actual vs forecast ----------
with t2:
    if pairs_hz.empty:
        st.info("No matched forecast/observation pairs in this range yet – keep the ingestion running.")
    else:
        pick = st.radio("Parameter", list(PARAMS), horizontal=True)
        _, unit, clr, fcol, ocol = PARAMS[pick]
        g = pairs_hz
        fig = go.Figure()
        fig.add_scatter(x=g.target_time, y=g[ocol], name="Actual", line=dict(color=clr, width=3))
        fig.add_scatter(x=g.target_time, y=g[fcol], name=f"Forecast ({hz} h ahead)",
                        line=dict(color="#ffa15a", dash="dash", width=2))
        fig.update_layout(height=430, hovermode="x unified", yaxis_title=f"{pick} ({unit})",
                          margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h"))
        fig.update_xaxes(rangeslider_visible=True)
        st.plotly_chart(fig, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Forecast error over time** (forecast − actual)")
            e = g[fcol] - g[ocol]
            ef = go.Figure(go.Bar(x=g.target_time, y=e,
                                  marker_color=np.where(e >= 0, "#ef553b", "#636efa")))
            ef.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), yaxis_title=f"Error ({unit})")
            st.plotly_chart(ef, use_container_width=True)
        with c2:
            st.markdown("**Forecast vs actual scatter**")
            lo = float(np.nanmin([g[ocol].min(), g[fcol].min()]))
            hi = float(np.nanmax([g[ocol].max(), g[fcol].max()]))
            sf = go.Figure()
            sf.add_scatter(x=g[ocol], y=g[fcol], mode="markers", marker=dict(color=clr), name="pairs")
            sf.add_scatter(x=[lo, hi], y=[lo, hi], mode="lines", line=dict(color="gray", dash="dot"),
                           name="perfect")
            sf.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="Actual",
                             yaxis_title="Forecast", showlegend=False)
            st.plotly_chart(sf, use_container_width=True)

# ---------- Tab 3: accuracy (Owner C's evaluation engine) ----------
with t3:
    if pairs_hz.empty:
        st.info("Not enough matched pairs to compute metrics yet.")
    else:
        st.caption("Metrics computed with Owner C's evaluation engine (`database/weather_db.py`).")
