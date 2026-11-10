"""
Seri Iskandar Weather Monitor - Streamlit dashboard (TFB2093 IoT Project, Owner: Aufa).

Dark "glassmorphism" redesign inspired by modern weather dashboard concepts.

Reads Owner C's SQLite database (database/weather.db) and uses Owner C's evaluation
engine (database/weather_db.py) for MAE, RMSE and the rain confusion matrix.
The live map makes a tiny read-only Open-Meteo call and NEVER writes to the
database, so the cronjob ingestion stays perfectly in sync.

Run from the repo root:   streamlit run dashboard/app.py
"""
import os
import sqlite3
import sys
from datetime import datetime, timedelta

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

LAT, LON = 4.3582, 100.9782  # Seri Iskandar, Perak

# display name -> (observations column, unit, colour, forecast col in view, observed col in view)
PARAMS = {
    "Temperature": ("temperature_c", "°C", "#ff7e5f", "fc_temp", "obs_temp"),
    "Humidity": ("humidity_pct", "%", "#4dd0e1", "fc_humidity", "obs_humidity"),
    "Rainfall": ("rainfall_mm", "mm", "#7c83ff", "fc_rain", "obs_rain"),
    "Wind speed": ("wind_speed_kmh", "km/h", "#b388ff", "fc_wind", "obs_wind"),
}

ACCENT = "#5ec8ff"

# ---------------- page & theme ----------------
st.set_page_config(page_title="Seri Iskandar Weather", page_icon="🌦️", layout="wide")

DARK_CSS = """
<style>
/* app background: deep blue gradient like the inspiration shot */
.stApp {
    background: radial-gradient(1200px 700px at 15% 0%, #16324f 0%,
                #0d1b2a 45%, #0a1220 100%) !important;
    color: #e8eef7;
}
#MainMenu, header, footer {visibility: hidden;}

/* glass cards */
.glass {
    background: linear-gradient(160deg, rgba(255,255,255,.10), rgba(255,255,255,.04));
    border: 1px solid rgba(255,255,255,.12);
    border-radius: 20px;
    padding: 18px 22px;
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    box-shadow: 0 8px 32px rgba(0,0,0,.35);
    color: #e8eef7;
}
.glass h3, .glass h4 {color:#e8eef7; margin:0 0 4px 0; font-weight:600;}
.glass .big {font-size:2.6rem; font-weight:700; line-height:1.1;}
.glass .unit {font-size:1.1rem; color:#9fb3c8;}
.glass .sub {color:#9fb3c8; font-size:.85rem; margin-top:2px;}

/* sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0e1c2e 0%, #0a1220 100%);
    border-right: 1px solid rgba(255,255,255,.08);
}
section[data-testid="stSidebar"] * {color:#cfe0f3 !important;}

/* metric cards */
div[data-testid="stMetric"]{
    background: linear-gradient(160deg, rgba(255,255,255,.10), rgba(255,255,255,.04));
    border: 1px solid rgba(255,255,255,.12);
    border-radius: 18px; padding: 16px 18px;
}
div[data-testid="stMetric"] label {color:#9fb3c8 !important;}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {color:#e8eef7 !important;}

/* forecast strip */
.day-card{
    background: linear-gradient(160deg, rgba(255,255,255,.09), rgba(255,255,255,.03));
    border:1px solid rgba(255,255,255,.10);
    border-radius:16px; padding:12px 10px; text-align:center;
}
.day-card .d{font-size:.8rem; color:#9fb3c8;}
.day-card .t{font-size:1.05rem; font-weight:700; color:#e8eef7;}
.day-card .n{font-size:.75rem; color:#8fa3b8;}

/* transparent plotly backgrounds */
.js-plotly-plot .plotly .bg, .main-svg {background:transparent !important;}
div[data-testid="stPlotlyChart"] {background:transparent;}
</style>
"""
st.markdown(DARK_CSS, unsafe_allow_html=True)

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#cfe0f3"),
    xaxis=dict(gridcolor="rgba(255,255,255,.08)", zerolinecolor="rgba(255,255,255,.15)"),
    yaxis=dict(gridcolor="rgba(255,255,255,.08)", zerolinecolor="rgba(255,255,255,.15)"),
    legend=dict(orientation="h", bgcolor="rgba(0,0,0,0)"),
    margin=dict(l=10, r=10, t=30, b=10),
)


def glass(cls: str, html: str):
    return f'<div class="glass {cls}">{html}</div>'


WMO = {  # WMO weather code -> (emoji, description)
    0: ("☀️", "Clear sky"), 1: ("🌤️", "Mainly clear"), 2: ("⛅", "Partly cloudy"),
    3: ("☁️", "Overcast"), 45: ("🌫️", "Fog"), 48: ("🌫️", "Rime fog"),
    51: ("🌦️", "Light drizzle"), 53: ("🌦️", "Drizzle"), 55: ("🌦️", "Heavy drizzle"),
    61: ("🌧️", "Light rain"), 63: ("🌧️", "Rain"), 65: ("🌧️", "Heavy rain"),
    80: ("🌦️", "Rain showers"), 81: ("🌧️", "Showers"), 82: ("⛈️", "Violent showers"),
    95: ("⛈️", "Thunderstorm"), 96: ("⛈️", "Thunderstorm + hail"), 99: ("⛈️", "Severe storm"),
}


def condition_from_row(r) -> str:
    """Pick an emoji + label from a DB row (rainfall / humidity based)."""
    rain = r.get("rainfall_mm", 0) or 0
    hum = r.get("humidity_pct", 0) or 0
    if rain >= 5:
        return "⛈️", "Thunder Storm Clouds"
    if rain >= 0.5:
        return "🌧️", "Rainy Storm Clouds"
    if rain > 0:
        return "🌦️", "Light Showers"
    if hum >= 95:
        return "🌫️", "Humid / Misty"
    if hum >= 80:
        return "☁️", "Cloudy"
    return "🌤️", "Partly Cloudy"


def feels_like(t_c: float, rh: float) -> float:
    """Heat index (Steadman approx.) - a small added analytics feature."""
    if t_c < 20:
        return t_c
    return t_c + 0.33 * (rh / 100 * 6.105) * np.exp(t_c / 16)  # simplified apparent temp


# ---------------- data layer ----------------
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


@st.cache_data(ttl=900)
def load_live_map():
    """Unique feature: live temperature map around Seri Iskandar.
    Read-only Open-Meteo call; nothing is written to the database."""
    lats, lons = [], []
    for dlat in np.linspace(-0.25, 0.25, 5):
        for dlon in np.linspace(-0.25, 0.25, 5):
            lats.append(LAT + dlat)
            lons.append(LON + dlon)
    url = ("https://api.open-meteo.com/v1/forecast"
           f"?latitude={','.join(f'{x:.3f}' for x in lats)}"
           f"&longitude={','.join(f'{x:.3f}' for x in lons)}"
           "&current=temperature_2m,relative_humidity_2m,weather_code"
           "&timezone=Asia%2FKuala_Lumpur")
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        js = r.json()
        if isinstance(js, dict):
            js = [js]
        rows = []
        for lat, lon, cur in zip(lats, lons, js):
            c = cur["current"]
            rows.append({"lat": lat, "lon": lon,
                         "temp": c["temperature_2m"], "rh": c["relative_humidity_2m"],
                         "code": c.get("weather_code", 0)})
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


def fmt(x, d=2):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    return f"{x:.{d}f}"


obs_all, fc_all, pairs_all = load(DB_PATH)

# ---------------- sidebar ----------------
with st.sidebar:
    st.markdown("## 🌦️ Weatherly")
    st.caption("Seri Iskandar · TFB2093 IoT")
    st.divider()
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
    st.divider()
    st.caption(f"📍 {loc}, Perak (4.37°N, 100.97°E)")
    st.caption(f"🗄️ DB: `{os.path.basename(DB_PATH)}`")

obs_f = obs[(obs["obs_time"].dt.date >= d0) & (obs["obs_time"].dt.date <= d1)]
pairs_f = pairs[(pairs["target_time"].dt.date >= d0) & (pairs["target_time"].dt.date <= d1)]
pairs_hz = pairs_f[pairs_f["lead_time_hours"] == hz].sort_values("target_time") if hz is not None else pairs_f.iloc[0:0]

# ---------------- header ----------------
st.markdown('<h1 style="color:#e8eef7;font-weight:800;">🌦️ Seri Iskandar Weather Monitor</h1>',
            unsafe_allow_html=True)
st.caption("Open-Meteo observations vs. forecasts · TFB2093 Internet-of-Things")
if using_demo:
    st.warning("database/weather.db not found – showing **demo data** from Owner C's demo builder.")

# ================= HERO CARD =================
last = obs.iloc[-1]
prev = obs.iloc[-2] if len(obs) > 1 else last
emoji, cond = condition_from_row(last)

hero_l, hero_r = st.columns([1.05, 2.0], gap="large")

with hero_l:
    fl = feels_like(last.temperature_c, last.humidity_pct)
    st.markdown(glass("hero", f"""
        <div style="font-size:4.2rem;line-height:1;">{emoji}</div>
        <div class="big">{fmt(last.temperature_c, 1)}<span class="unit"> °C</span></div>
        <div class="sub">🌡️ Feels like {fmt(fl, 1)} °C</div>
        <div style="margin-top:10px;font-weight:600;">{cond}</div>
        <div class="sub">📍 {loc}, Perak</div>
        <div class="sub">🕘 {last['obs_time']:%d %b %Y · %H:%M}</div>
    """), unsafe_allow_html=True)

with hero_r:
    k1, k2, k3, k4 = st.columns(4)

    def delta(col, d=1):
        if pd.isna(last[col]) or pd.isna(prev[col]):
            return None
        return f"{last[col] - prev[col]:+.{d}f}"

    k1.markdown(glass("", f"""
        <h4>💨 Wind Status</h4>
        <div class="big" style="font-size:2rem;">{fmt(last.wind_speed_kmh, 1)}</div>
        <div class="unit">km/h</div>
        <div class="sub">Δ {delta('wind_speed_kmh') or '–'} km/h vs prev. hour</div>
    """), unsafe_allow_html=True)

    k2.markdown(glass("", f"""
        <h4>💧 Humidity</h4>
        <div class="big" style="font-size:2rem;">{fmt(last.humidity_pct, 0)}</div>
        <div class="unit">%</div>
        <div class="sub">Δ {delta('humidity_pct', 0) or '–'} % vs prev. hour</div>
    """), unsafe_allow_html=True)

    # rain probability gauge replaces 'UV Index' (matches assignment parameters)
    nxt_all = (fc[fc["target_time"] > last["obs_time"]]
               .sort_values(["target_time", "lead_time_hours"])
               .drop_duplicates("target_time"))
    prob_now = nxt_all.iloc[0]["rain_probability_pct"] if not nxt_all.empty else np.nan
    k3.markdown(glass("", f"""
        <h4>☔ Rain Chance</h4>
        <div class="big" style="font-size:2rem;">{fmt(prob_now, 0) if pd.notna(prob_now) else '–'}</div>
        <div class="unit">%</div>
        <div class="sub">next-hour forecast probability</div>
    """), unsafe_allow_html=True)

    k4.markdown(glass("", f"""
        <h4>🌧️ Rainfall</h4>
        <div class="big" style="font-size:2rem;">{fmt(last.rainfall_mm, 1)}</div>
        <div class="unit">mm</div>
        <div class="sub">Δ {delta('rainfall_mm') or '–'} mm vs prev. hour</div>
    """), unsafe_allow_html=True)

    # next forecast banner
    if not nxt_all.empty:
        n = nxt_all.iloc[0]
        prob = f" · {n.rain_probability_pct:.0f}% chance of rain" if pd.notna(n.rain_probability_pct) else ""
        st.info(f"**Next forecast ({n['target_time']:%d %b %H:%M}):** {fmt(n.temperature_c, 1)} °C · "
                f"{fmt(n.humidity_pct, 0)}% · {fmt(n.rainfall_mm, 1)} mm · "
                f"{fmt(n.wind_speed_kmh, 1)} km/h{prob}")
        rain_soon = nxt_all.head(6)["rainfall_mm"].max()
        if pd.notna(rain_soon) and rain_soon >= rain_thr:
            st.warning("☔ Rain expected within the next 6 hours.")

# ================= 7-DAY FORECAST STRIP =================
st.markdown('<h3 style="color:#e8eef7;margin-top:18px;">📅 Multi-day Forecast</h3>', unsafe_allow_html=True)
if not fc.empty:
    daily = (fc[fc["lead_time_hours"] <= 72]
             .assign(date=fc["target_time"].dt.date)
             .groupby("date")
             .agg(tmax=("temperature_c", "max"), tmin=("temperature_c", "min"),
                  rain=("rainfall_mm", "sum"), prob=("rain_probability_pct", "max"))
             .head(7))
    cols = st.columns(len(daily))
    for i, (d, r) in enumerate(daily.iterrows()):
        e = "🌧️" if r.rain >= 1 else ("🌦️" if r.rain > 0 else "🌤️")
        cols[i].markdown(glass("", f"""
            <div class="d">{d.strftime('%a %d %b')}</div>
            <div style="font-size:1.6rem;">{e}</div>
            <div class="t">{r.tmax:.0f}° <span class="n">/ {r.tmin:.0f}°</span></div>
            <div class="n">{r.rain:.1f} mm · {r.prob:.0f}% rain</div>
        """), unsafe_allow_html=True)

# ================= LIVE MAP =================
st.markdown('<h3 style="color:#e8eef7;margin-top:18px;">🗺️ Live Weather Condition Map</h3>', unsafe_allow_html=True)
st.caption("Current temperature around Seri Iskandar from Open-Meteo (read-only, 5×5 grid, cached 15 min). "
           "This is a bonus feature: spatial context around the monitoring station.")
live = load_live_map()
if live.empty:
    st.info("Live map unavailable right now (network). The rest of the dashboard runs on the database.")
else:
    fig = go.Figure(go.Scattermapbox(
        lat=live.lat, lon=live.lon,
        mode="markers+text",
        text=[f"{t:.1f}°" for t in live.temp],
        textfont=dict(color="white", size=11),
        customdata=np.stack([live.temp, live.rh, live.code], axis=-1),
        hovertemplate="<b>%{customdata[0]:.1f} °C</b> · %{customdata[1]:.0f}%% RH"
                      "<br>WMO code %{customdata[2]}<extra></extra>",
        marker=dict(
            size=34, opacity=.85,
            color=live.temp, colorscale="Turbo", cmin=live.temp.min() - 1, cmax=live.temp.max() + 1,
            showscale=True, colorbar=dict(title="°C", thickness=12, x=1.0),
        ),
    ))
    fig.add_trace(go.Scattermapbox(
        lat=[LAT], lon=[LON], mode="markers",
        marker=dict(size=18, color="#ffffff", symbol="star"),
        name="Our station", hovertemplate="<b>Seri Iskandar station</b><extra></extra>"))
    fig.update_layout(height=420, mapbox=dict(style="carto-darkmatter", zoom=9.5,
                                              center=dict(lat=LAT, lon=LON)),
                      margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# ================= ANALYTICS TABS =================
t2, t3, t4 = st.tabs(["📈 Actual vs Forecast", "🎯 Accuracy", "💾 Data & Export"])

# ---------- Tab 2: actual vs forecast ----------
with t2:
    if pairs_hz.empty:
        st.info("No matched forecast/observation pairs in this range yet – keep the ingestion running.")
    else:
        pick = st.radio("Parameter", list(PARAMS), horizontal=True)
        _, unit, clr, fcol, ocol = PARAMS[pick]
        g = pairs_hz
        fig = go.Figure()
        fig.add_scatter(x=g.target_time, y=g[ocol], name="Actual",
                        line=dict(color=clr, width=3))
        fig.add_scatter(x=g.target_time, y=g[fcol], name=f"Forecast ({hz} h ahead)",
                        line=dict(color="#ffa15a", dash="dash", width=2))
        fig.update_layout(height=430, hovermode="x unified", yaxis_title=f"{pick} ({unit})",
                          **PLOTLY_LAYOUT)
        fig.update_xaxes(rangeslider_visible=True, gridcolor="rgba(255,255,255,.08)")
        st.plotly_chart(fig, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Forecast error over time** (forecast − actual)")
            e = g[fcol] - g[ocol]
            ef = go.Figure(go.Bar(x=g.target_time, y=e,
                                  marker_color=np.where(e >= 0, "#ff7e5f", "#5ec8ff")))
            ef.update_layout(height=280, yaxis_title=f"Error ({unit})", **PLOTLY_LAYOUT)
            st.plotly_chart(ef, use_container_width=True)
        with c2:
            st.markdown("**Forecast vs actual scatter**")
            lo = float(np.nanmin([g[ocol].min(), g[fcol].min()]))
            hi = float(np.nanmax([g[ocol].max(), g[fcol].max()]))
            sf = go.Figure()
            sf.add_scatter(x=g[ocol], y=g[fcol], mode="markers",
                           marker=dict(color=clr), name="pairs")
            sf.add_scatter(x=[lo, hi], y=[lo, hi], mode="lines",
                           line=dict(color="gray", dash="dot"), name="perfect")
            sf.update_layout(height=280, xaxis_title="Actual", yaxis_title="Forecast",
                             showlegend=False, **PLOTLY_LAYOUT)
            st.plotly_chart(sf, use_container_width=True)

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
            colours = {"Temperature (°C)": PARAMS["Temperature"][2],
                       "Humidity (%)": PARAMS["Humidity"][2],
                       "Wind Speed (km/h)": PARAMS["Wind speed"][2]}
            for var, s in by_lead.groupby("Variable"):
                fig.add_scatter(x=s["Lead (h)"], y=s.MAE, mode="lines+markers", name=var,
                                line=dict(color=colours.get(var)))
            fig.update_layout(height=320, xaxis_title="Lead time (h)", yaxis_title="MAE",
                              **PLOTLY_LAYOUT)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(by_lead, use_container_width=True, hide_index=True)

        st.subheader(f"Rain confusion matrix · {hz} h lead time · threshold {rain_thr} mm")
        cm = wdb.rain_confusion_matrix(pairs_hz, threshold_mm=rain_thr)
        cmdf = wdb.confusion_matrix_df(cm)
        hm = go.Figure(go.Heatmap(
            z=cmdf.values, x=list(cmdf.columns), y=list(cmdf.index), text=cmdf.values,
            texttemplate="%{text}", colorscale="Blues", showscale=False))
        hm.update_layout(height=320, yaxis=dict(autorange="reversed"), **PLOTLY_LAYOUT)
        a, b = st.columns([3, 2])
        a.plotly_chart(hm, use_container_width=True)
        acc = cm["Accuracy"]
        b.metric("Accuracy", fmt(acc * 100 if acc is not None else None, 1) + " %")
        b.metric("Precision", fmt(cm["Precision"]))
        b.metric("Recall (POD)", fmt(cm["Recall (POD)"]))
        b.metric("False Alarm Ratio", fmt(cm["False Alarm Ratio"]))

# ---------- Tab 4: data & export ----------
with t4:
    st.subheader("Historical observations")
    st.dataframe(obs_f.sort_values("obs_time", ascending=False), use_container_width=True,
                 hide_index=True)
    st.download_button("⬇️ Export observations (CSV)", obs_f.to_csv(index=False).encode(),
                       "observations.csv", "text/csv")
    if not pairs_f.empty:
        st.download_button("⬇️ Export forecast-vs-actual (CSV)", pairs_f.to_csv(index=False).encode(),
                           "forecast_vs_actual.csv", "text/csv")
        st.download_button("⬇️ Export error metrics by lead time (CSV)",
                           wdb.error_metrics(pairs_f, by_lead_time=True).to_csv(index=False).encode(),
                           "error_metrics.csv", "text/csv")
