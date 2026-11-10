"""Seri Iskandar Weather Monitor - Streamlit dashboard (TFB2093 IoT Project, Owner: Aufa).

Reads Owner C's SQLite database (database/weather.db) and uses Owner C's evaluation
engine (database/weather_db.py) for MAE, RMSE and the rain confusion matrix.

Run from the repo root:   streamlit run dashboard/app.py
"""
import os
import sqlite3
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ---------- link to Owner C's module ----------
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "database"))
import weather_db as wdb  # noqa: E402  (Owner C: schema, load_pairs, error_metrics, rain_confusion_matrix)

DB_PATH = os.environ.get("WEATHER_DB", wdb.DB_PATH)

# display name -> (observations column, unit, colour, forecast col in view, observed col in view)
PARAMS = {
    "Temperature": ("temperature_c", "°C", "#ef553b", "fc_temp", "obs_temp"),
    "Humidity": ("humidity_pct", "%", "#00cc96", "fc_humidity", "obs_humidity"),
    "Rainfall": ("rainfall_mm", "mm", "#636efa", "fc_rain", "obs_rain"),
    "Wind speed": ("wind_speed_kmh", "km/h", "#ab63fa", "fc_wind", "obs_wind"),
}

st.set_page_config(page_title="Seri Iskandar Weather", page_icon="🌦️", layout="wide")
st.markdown(
    """<style>
    div[data-testid="stMetric"]{background:rgba(120,130,160,.12);border-radius:14px;padding:14px 18px}
    .block-container{padding-top:1.5rem}
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
    st.subheader(f"Latest reading · {last['obs_time']:%d %b %Y, %H:%M}")
    c = st.columns(4)

    def delta(col, d=1):
        if pd.isna(last[col]) or pd.isna(prev[col]):
            return None
        return f"{last[col] - prev[col]:+.{d}f}"

    c[0].metric("🌡️ Temperature", f"{fmt(last.temperature_c, 1)} °C", delta("temperature_c"))
    c[1].metric("💧 Humidity", f"{fmt(last.humidity_pct, 0)} %", delta("humidity_pct", 0))
    c[2].metric("🌧️ Rainfall", f"{fmt(last.rainfall_mm, 1)} mm", delta("rainfall_mm"),
                delta_color="inverse")
    c[3].metric("💨 Wind speed", f"{fmt(last.wind_speed_kmh, 1)} km/h", delta("wind_speed_kmh"))

    # most recent forecast for each upcoming hour = smallest lead time
    nxt = (fc[fc["target_time"] > last["obs_time"]]
           .sort_values(["target_time", "lead_time_hours"])
           .drop_duplicates("target_time"))
    if not nxt.empty:
        n = nxt.iloc[0]
        prob = f" · {n.rain_probability_pct:.0f}% chance of rain" if pd.notna(n.rain_probability_pct) else ""
        st.info(f"**Next forecast ({n['target_time']:%d %b %H:%M}):** {fmt(n.temperature_c, 1)} °C · "
                f"{fmt(n.humidity_pct, 0)}% · {fmt(n.rainfall_mm, 1)} mm · "
                f"{fmt(n.wind_speed_kmh, 1)} km/h{prob}")
        rain_soon = nxt.head(6)["rainfall_mm"].max()
        if pd.notna(rain_soon) and rain_soon >= rain_thr:
            st.warning("☔ Rain expected within the next 6 hours.")

    st.subheader("Last 24 h")
    day = obs[obs["obs_time"] >= obs["obs_time"].max() - pd.Timedelta(hours=24)]
    fig = go.Figure()
    for nme in ("Temperature", "Humidity"):
        col, u, clr, _, _ = PARAMS[nme]
        fig.add_scatter(x=day.obs_time, y=day[col], name=f"{nme} ({u})", line=dict(color=clr))
    fig.add_bar(x=day.obs_time, y=day.rainfall_mm, name="Rainfall (mm)",
                marker_color=PARAMS["Rainfall"][2], opacity=.5)
    fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0), hovermode="x unified",
                      legend=dict(orientation="h"))
    st.plotly_chart(fig, width="stretch")

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
        st.plotly_chart(fig, width="stretch")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Forecast error over time** (forecast − actual)")
            e = g[fcol] - g[ocol]
            ef = go.Figure(go.Bar(x=g.target_time, y=e,
                                  marker_color=np.where(e >= 0, "#ef553b", "#636efa")))
            ef.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), yaxis_title=f"Error ({unit})")
            st.plotly_chart(ef, width="stretch")
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
            st.plotly_chart(sf, width="stretch")

# ---------- Tab 3: accuracy (Owner C's evaluation engine) ----------
with t3:
    if pairs_hz.empty:
        st.info("Not enough matched pairs to compute metrics yet.")
    else:
        st.caption("Metrics computed with Owner C's evaluation engine (`database/weather_db.py`).")
        em = wdb.error_metrics(pairs_hz)
        st.subheader(f"Error metrics · {hz} h lead time · {int(em['n'].max())} pairs")
        cols = st.columns(len(em))
        for i, r in enumerate(em.itertuples(index=False)):
            cols[i].metric(r.Variable, f"MAE {r.MAE:.2f}", f"RMSE {r.RMSE:.2f}", delta_color="off")

        by_lead = wdb.error_metrics(pairs_f, by_lead_time=True)
        if not by_lead.empty:
            st.markdown("**MAE by forecast lead time**")
            fig = go.Figure()
            colours = {"Temperature (°C)": PARAMS["Temperature"][2], "Humidity (%)": PARAMS["Humidity"][2],
                       "Wind Speed (km/h)": PARAMS["Wind speed"][2]}
            for var, s in by_lead.groupby("Variable"):
                fig.add_scatter(x=s["Lead (h)"], y=s.MAE, mode="lines+markers", name=var,
                                line=dict(color=colours.get(var)))
            fig.update_layout(height=320, xaxis_title="Lead time (h)", yaxis_title="MAE",
                              margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h"))
            st.plotly_chart(fig, width="stretch")
            st.dataframe(by_lead, width="stretch", hide_index=True)

        st.subheader(f"Rain confusion matrix · {hz} h lead time · threshold {rain_thr} mm")
        cm = wdb.rain_confusion_matrix(pairs_hz, threshold_mm=rain_thr)
        cmdf = wdb.confusion_matrix_df(cm)
        hm = go.Figure(go.Heatmap(
            z=cmdf.values, x=list(cmdf.columns), y=list(cmdf.index), text=cmdf.values,
            texttemplate="%{text}", colorscale="Blues", showscale=False))
        hm.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), yaxis=dict(autorange="reversed"))
        a, b = st.columns([3, 2])
        a.plotly_chart(hm, width="stretch")
        acc = cm["Accuracy"]
        b.metric("Accuracy", fmt(acc * 100 if acc is not None else None, 1) + " %")
        b.metric("Precision", fmt(cm["Precision"]))
        b.metric("Recall (POD)", fmt(cm["Recall (POD)"]))
        b.metric("False Alarm Ratio", fmt(cm["False Alarm Ratio"]))

# ---------- Tab 4: data & export ----------
with t4:
    st.subheader("Historical observations")
    st.dataframe(obs_f.sort_values("obs_time", ascending=False), width="stretch", hide_index=True)
    st.download_button("⬇️ Export observations (CSV)", obs_f.to_csv(index=False).encode(),
                       "observations.csv", "text/csv")
    if not pairs_f.empty:
        st.download_button("⬇️ Export forecast-vs-actual (CSV)", pairs_f.to_csv(index=False).encode(),
                           "forecast_vs_actual.csv", "text/csv")
        st.download_button("⬇️ Export error metrics by lead time (CSV)",
                           wdb.error_metrics(pairs_f, by_lead_time=True).to_csv(index=False).encode(),
                           "error_metrics.csv", "text/csv")
