"""Seri Iskandar Weather Monitor - Streamlit dashboard (TFB2093 IoT Project)."""
import os
import sqlite3

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from demo_data import build_demo_db

DB_PATH = os.environ.get("WEATHER_DB", "weather.db")
PARAMS = {
    "Temperature": ("temperature", "°C", "#ef553b"),
    "Humidity": ("humidity", "%", "#00cc96"),
    "Rainfall": ("rainfall", "mm", "#636efa"),
    "Wind speed": ("wind_speed", "km/h", "#ab63fa"),
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
    build_demo_db(DB_PATH)
    using_demo = True


@st.cache_data(ttl=60)
def load(db_path: str):
    con = sqlite3.connect(db_path)
    obs = pd.read_sql("SELECT * FROM observations", con, parse_dates=["timestamp"])
    fc = pd.read_sql("SELECT * FROM forecasts", con, parse_dates=["fetched_at", "target_time"])
    con.close()
    return obs.sort_values("timestamp"), fc.sort_values("target_time")


def merge(obs, fc):
    """Hourly-average observations, join to forecasts on target hour."""
    o = obs.copy()
    o["hour"] = o["timestamp"].dt.floor("h")
    o = o.groupby("hour")[[v[0] for v in PARAMS.values()]].mean().reset_index()
    f = fc.copy()
    f["hour"] = f["target_time"].dt.floor("h")
    f = f.groupby(["hour", "horizon_hours"])[[v[0] for v in PARAMS.values()]].mean().reset_index()
    return f.merge(o, on="hour", suffixes=("_fc", "_obs"))


def error_table(m):
    rows = []
    for name, (col, unit, _) in PARAMS.items():
        for hz, g in m.groupby("horizon_hours"):
            e = g[f"{col}_fc"] - g[f"{col}_obs"]
            rows.append({"Parameter": name, "Horizon (h)": hz, "N": len(g),
                         "MAE": e.abs().mean(), "RMSE": np.sqrt((e ** 2).mean()), "Bias": e.mean()})
    return pd.DataFrame(rows)


def rain_confusion(m, thr):
    a = m["rainfall_obs"] >= thr
    p = m["rainfall_fc"] >= thr
    tp, fp = int((a & p).sum()), int((~a & p).sum())
    fn, tn = int((a & ~p).sum()), int((~a & ~p).sum())
    n = tp + fp + fn + tn
    prec = tp / (tp + fp) if tp + fp else np.nan
    rec = tp / (tp + fn) if tp + fn else np.nan
    f1 = 2 * prec * rec / (prec + rec) if prec == prec and rec == rec and prec + rec else np.nan
    return dict(tp=tp, fp=fp, fn=fn, tn=tn, acc=(tp + tn) / n if n else np.nan,
                prec=prec, rec=rec, f1=f1)


def fmt(x, d=2):
    return "–" if x is None or x != x else f"{x:.{d}f}"


obs, fc = load(DB_PATH)

# ---------- sidebar ----------
with st.sidebar:
    st.title("🌦️ Controls")
    if obs.empty:
        st.error("No observations in database yet.")
        st.stop()
    dmin, dmax = obs["timestamp"].min().date(), obs["timestamp"].max().date()
    rng = st.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)
    if isinstance(rng, tuple) and len(rng) == 2:
        d0, d1 = rng
    else:
        d0 = d1 = rng[0] if isinstance(rng, tuple) else rng
    horizons = sorted(fc["horizon_hours"].unique()) if not fc.empty else []
    hz = st.selectbox("Forecast horizon (hours ahead)", horizons,
                      index=len(horizons) - 1 if horizons else 0) if horizons else None
    rain_thr = st.slider("Rain threshold (mm/h)", 0.1, 2.0, 0.1, 0.1,
                         help="Hour counts as 'rain' if rainfall ≥ this value.")
    if st.button("🔄 Refresh data"):
        st.cache_data.clear(); st.rerun()
    st.caption(f"Location: Seri Iskandar, Perak (4.37°N, 100.97°E)\nDB: `{DB_PATH}`")

mask = (obs["timestamp"].dt.date >= d0) & (obs["timestamp"].dt.date <= d1)
obs_f = obs[mask]
fc_f = fc[(fc["target_time"].dt.date >= d0) & (fc["target_time"].dt.date <= d1)] if not fc.empty else fc
merged = merge(obs_f, fc_f) if not fc_f.empty and not obs_f.empty else pd.DataFrame()

# ---------- header ----------
st.title("🌦️ Seri Iskandar Weather Monitor")
st.caption("Open-Meteo observations vs. forecasts · TFB2093 Internet-of-Things")
if using_demo:
    st.warning("weather.db not found – showing **demo data**. Place the collector's real "
               "`weather.db` next to app.py (or set WEATHER_DB) to show live data.")

# ---------- tabs ----------
t1, t2, t3, t4 = st.tabs(["📍 Current", "📈 Actual vs Forecast", "🎯 Accuracy", "💾 Data & Export"])

with t1:
    last = obs.iloc[-1]
    prev = obs.iloc[-2] if len(obs) > 1 else last
    st.subheader(f"Latest reading · {last['timestamp']:%d %b %Y, %H:%M}")
    c = st.columns(4)
    c[0].metric("🌡️ Temperature", f"{last.temperature:.1f} °C", f"{last.temperature - prev.temperature:+.1f}")
    c[1].metric("💧 Humidity", f"{last.humidity:.0f} %", f"{last.humidity - prev.humidity:+.0f}")
    c[2].metric("🌧️ Rainfall", f"{last.rainfall:.1f} mm", f"{last.rainfall - prev.rainfall:+.1f}",
                delta_color="inverse")
    c[3].metric("💨 Wind speed", f"{last.wind_speed:.1f} km/h", f"{last.wind_speed - prev.wind_speed:+.1f}")
    if not fc.empty:
        nxt = fc[fc["target_time"] > last["timestamp"]].sort_values("target_time")
        if not nxt.empty:
            n = nxt.iloc[0]
            st.info(f"**Next forecast ({n['target_time']:%d %b %H:%M}):** {n.temperature:.1f} °C · "
                    f"{n.humidity:.0f}% · {n.rainfall:.1f} mm · {n.wind_speed:.1f} km/h")
        rain_soon = nxt.head(6)["rainfall"].max() if not nxt.empty else 0
        if rain_soon >= rain_thr:
            st.warning("☔ Rain expected within the next forecast hours.")
    st.subheader("Last 24 h")
    day = obs[obs["timestamp"] >= obs["timestamp"].max() - pd.Timedelta(hours=24)]
    fig = go.Figure()
    for nme, (col, u, clr) in list(PARAMS.items())[:2]:
        fig.add_scatter(x=day.timestamp, y=day[col], name=f"{nme} ({u})", line=dict(color=clr))
    fig.add_bar(x=day.timestamp, y=day.rainfall, name="Rainfall (mm)", marker_color=PARAMS["Rainfall"][2],
                opacity=.5)
    fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0), hovermode="x unified",
                      legend=dict(orientation="h"))
    st.plotly_chart(fig, width="stretch")

with t2:
    if merged.empty:
        st.info("No matched forecast/observation pairs in this range yet.")
    else:
        pick = st.radio("Parameter", list(PARAMS), horizontal=True)
        col, unit, clr = PARAMS[pick]
        g = merged[merged.horizon_hours == hz].sort_values("hour")
        fig = go.Figure()
        fig.add_scatter(x=g.hour, y=g[f"{col}_obs"], name="Actual", line=dict(color="#222" if False else clr, width=3))
        fig.add_scatter(x=g.hour, y=g[f"{col}_fc"], name=f"Forecast ({hz} h ahead)",
                        line=dict(color="#ffa15a", dash="dash", width=2))
        fig.update_layout(height=430, hovermode="x unified", yaxis_title=f"{pick} ({unit})",
                          margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h"))
        fig.update_xaxes(rangeslider_visible=True)
        st.plotly_chart(fig, width="stretch")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Forecast error over time**")
            e = g[f"{col}_fc"] - g[f"{col}_obs"]
            ef = go.Figure(go.Bar(x=g.hour, y=e, marker_color=np.where(e >= 0, "#ef553b", "#636efa")))
            ef.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), yaxis_title=f"Error ({unit})")
            st.plotly_chart(ef, width="stretch")
        with c2:
            st.markdown("**Forecast vs actual scatter**")
            lo = float(min(g[f"{col}_obs"].min(), g[f"{col}_fc"].min()))
            hi = float(max(g[f"{col}_obs"].max(), g[f"{col}_fc"].max()))
            sf = go.Figure()
            sf.add_scatter(x=g[f"{col}_obs"], y=g[f"{col}_fc"], mode="markers", marker=dict(color=clr), name="pairs")
            sf.add_scatter(x=[lo, hi], y=[lo, hi], mode="lines", line=dict(color="gray", dash="dot"), name="perfect")
            sf.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="Actual",
                             yaxis_title="Forecast", showlegend=False)
            st.plotly_chart(sf, width="stretch")

with t3:
    if merged.empty:
        st.info("Not enough data to compute metrics.")
    else:
        et = error_table(merged)
        sel = et[et["Horizon (h)"] == hz]
        st.subheader(f"Error metrics · {hz} h horizon")
        cols = st.columns(4)
        for i, (nme, (col, u, _)) in enumerate(PARAMS.items()):
            r = sel[sel.Parameter == nme].iloc[0]
            cols[i].metric(nme, f"MAE {r.MAE:.2f} {u}", f"RMSE {r.RMSE:.2f}", delta_color="off")
        st.markdown("**MAE by forecast horizon**")
        fig = go.Figure()
        for nme, (_, u, clr) in PARAMS.items():
            s = et[et.Parameter == nme]
            fig.add_scatter(x=s["Horizon (h)"], y=s.MAE, mode="lines+markers", name=f"{nme} ({u})",
                            line=dict(color=clr))
        fig.update_layout(height=320, xaxis_title="Horizon (h)", yaxis_title="MAE",
                          margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h"))
        st.plotly_chart(fig, width="stretch")
        st.dataframe(et.round(3), width="stretch", hide_index=True)

        st.subheader(f"Rain confusion matrix · {hz} h horizon · threshold {rain_thr} mm")
        cm = rain_confusion(merged[merged.horizon_hours == hz], rain_thr)
        z = [[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]]
        hm = go.Figure(go.Heatmap(z=z, x=["Pred: No rain", "Pred: Rain"], y=["Actual: No rain", "Actual: Rain"],
                                  text=z, texttemplate="%{text}", colorscale="Blues", showscale=False))
        hm.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), yaxis=dict(autorange="reversed"))
        a, b = st.columns([3, 2])
        a.plotly_chart(hm, width="stretch")
        b.metric("Accuracy", fmt(cm["acc"] * 100 if cm["acc"] == cm["acc"] else None, 1) + " %")
        b.metric("Precision", fmt(cm["prec"]))
        b.metric("Recall (hit rate)", fmt(cm["rec"]))
        b.metric("F1-score", fmt(cm["f1"]))

with t4:
    st.subheader("Historical observations")
    st.dataframe(obs_f.sort_values("timestamp", ascending=False), width="stretch", hide_index=True)
    st.download_button("⬇️ Export observations (CSV)", obs_f.to_csv(index=False).encode(),
                       "observations.csv", "text/csv")
    if not merged.empty:
        st.download_button("⬇️ Export forecast-vs-actual (CSV)", merged.to_csv(index=False).encode(),
                           "forecast_vs_actual.csv", "text/csv")
        st.download_button("⬇️ Export error metrics (CSV)", error_table(merged).to_csv(index=False).encode(),
                           "error_metrics.csv", "text/csv")
