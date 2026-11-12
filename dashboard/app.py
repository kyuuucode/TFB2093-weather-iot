"""Seri Iskandar Weather Monitor - Streamlit dashboard (TFB2093 IoT Project).

Dark glassmorphism theme + Apache ECharts (streamlit-echarts); light mode is switchable
from the sidebar. Data comes from the weather.db that the hourly cronjob commits to GitHub
(falls back to the bundled DB offline). MAE / RMSE / confusion matrix come from Owner C's
`database/weather_db.py` - no evaluation logic is duplicated here.

Layout (all UI code lives in dashboard/weather_ui/):
    config.py          constants (coordinates, DB url, parameter table)
    theme.py           dark / light colour tokens + CSS
    data.py            DB sync + loading
    sun.py             sunrise / sunset
    sidebar.py         toggle + filters
    hero.py            weather card, Sun Times, KPI cards, Next forecast, reminder
    forecast_strip.py  multi-day forecast cards
    tabs.py            Current / Actual vs Forecast / Accuracy / Data & Export
    charts.py          ECharts helpers
    scroll_lock.py     keeps the scroll position on rerun

Run from the repo root:   streamlit run dashboard/app.py
Requirements: streamlit pandas numpy requests streamlit-echarts
"""
import streamlit as st

# must be the first Streamlit call
st.set_page_config(page_title="Seri Iskandar Weather", page_icon="🌦️", layout="wide")

from weather_ui.data import load, resolve_db_path  # noqa: E402
from weather_ui.forecast_strip import render_multiday  # noqa: E402
from weather_ui.hero import render_hero  # noqa: E402
from weather_ui.scroll_lock import keep_scroll_position  # noqa: E402
from weather_ui.sidebar import render_sidebar  # noqa: E402
from weather_ui.tabs import render_tabs  # noqa: E402
from weather_ui.theme import build_css, get_theme  # noqa: E402

# ---------- theme (sidebar toggle; default dark) ----------
if "light_mode" not in st.session_state:
    st.session_state.light_mode = False
MODE = "light" if st.session_state.light_mode else "dark"
T = get_theme(MODE)
st.markdown(build_css(MODE), unsafe_allow_html=True)

# auto-refresh every 5 minutes so new hourly data appears on its own
st.markdown('<meta http-equiv="refresh" content="300">', unsafe_allow_html=True)

# ---------- data ----------
DB_PATH, using_demo = resolve_db_path()
obs_all, fc_all, pairs_all = load(DB_PATH)

# ---------- sidebar / filters ----------
f = render_sidebar(obs_all, pairs_all, DB_PATH)
obs = obs_all[obs_all["location"] == f.loc]
fc = fc_all[fc_all["location"] == f.loc]
pairs = pairs_all[pairs_all["location"] == f.loc]

obs_f = obs[(obs["obs_time"].dt.date >= f.d0) & (obs["obs_time"].dt.date <= f.d1)]
pairs_f = pairs[(pairs["target_time"].dt.date >= f.d0) & (pairs["target_time"].dt.date <= f.d1)]
pairs_hz = (pairs_f[pairs_f["lead_time_hours"] == f.hz].sort_values("target_time")
            if f.hz is not None else pairs_f.iloc[0:0])

# ---------- page ----------
st.markdown('<h1 style="font-weight:800;">🌦️ Seri Iskandar Weather Monitor</h1>', unsafe_allow_html=True)
st.caption("Open-Meteo observations vs. forecasts · TFB2093 Internet-of-Things · "
           "live-synced with the ingestion database")
if using_demo:
    st.warning("database/weather.db not found – showing **demo data** from Owner C's demo builder.")

sel_day, accent = render_hero(T, obs, fc, f.d1, f.rain_thr, DB_PATH)
render_multiday(fc, sel_day, accent)
render_tabs(T, obs, obs_f, pairs_f, pairs_hz, f.hz, f.rain_thr)

keep_scroll_position()
