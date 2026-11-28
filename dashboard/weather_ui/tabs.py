"""The four dashboard tabs (Current / Actual vs Forecast / Accuracy / Data & Export)."""
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_echarts import st_echarts

from .charts import area_line, axis, base_options, tooltip, yaxis
from .config import PARAMS
from .data import wdb
from .helpers import fmt, glass

# Confusion-matrix geometry: the plot area is fixed so the 2x2 metric cards line up with it.
CM_H, CM_TOP, CM_BOTTOM, CM_LEFT = 300, 10, 34, 105
CM_PLOT_H = CM_H - CM_TOP - CM_BOTTOM  # 256px = two heatmap rows of 128px


def _hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lum(rgb):
    """WCAG relative luminance."""
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _heat_cell_rgb(ratio, stops):
    """Colour ECharts' visualMap gives a cell at `ratio` (0..1) along the colour stops."""
    rgbs = [_hex_rgb(c) for c in stops]
    pos = min(max(ratio, 0.0), 1.0) * (len(rgbs) - 1)
    i = min(int(pos), len(rgbs) - 2)
    f = pos - i
    return tuple(rgbs[i][k] + (rgbs[i + 1][k] - rgbs[i][k]) * f for k in range(3))


def _label_colour(ratio, T):
    """Pick light or dark text, whichever contrasts better with the cell colour."""
    cell = _heat_cell_rgb(ratio, T["heat"])
    light, dark = _hex_rgb(T["heat_label"]), _hex_rgb("#0b1620")
    return T["heat_label"] if _contrast(cell, light) >= _contrast(cell, dark) else "#0b1620"


def _tab_current(T, obs):
    day = obs[obs["obs_time"] >= obs["obs_time"].max() - pd.Timedelta(hours=24)]
    x = [t.isoformat() for t in day.obs_time]
    opt = {
        **base_options(T),
        "xAxis": axis(T, is_time=True),
        "yAxis": [
            {**yaxis(T, "°C / %"), "max": 100},
            {**yaxis(T, "mm"), "splitLine": {"show": False}},
        ],
        "series": [
            area_line(x, day.temperature_c.tolist(), "Temperature (°C)", PARAMS["Temperature"][2]),
            area_line(x, day.humidity_pct.tolist(), "Humidity (%)", PARAMS["Humidity"][2]),
            {"name": "Rainfall (mm)", "type": "bar", "yAxisIndex": 1, "barWidth": "55%",
             "itemStyle": {"color": PARAMS["Rainfall"][2], "opacity": .55, "borderRadius": [3, 3, 0, 0]},
             "data": [[xi, yi] for xi, yi in zip(x, day.rainfall_mm.tolist())]},
        ],
    }
    st_echarts(options=opt, height="360px")


def _tab_actual_vs_forecast(T, pairs_hz, hz):
    if pairs_hz.empty:
        st.info("No matched forecast/observation pairs in this range yet – keep the ingestion running.")
        return
    pick = st.radio("Parameter", list(PARAMS), horizontal=True)
    _, unit, clr, fcol, ocol = PARAMS[pick]
    g = pairs_hz
    gx = [t.isoformat() for t in g.target_time]

    opt = {
        **base_options(T),
        "xAxis": axis(T, is_time=True),
        "yAxis": yaxis(T, f"{pick} ({unit})"),
        "dataZoom": [{"type": "inside"}, {"type": "slider", "height": 18, "bottom": 2,
                                          "borderColor": "transparent",
                                          "backgroundColor": T["zoom_bg"]}],
        "series": [
            area_line(gx, g[ocol].tolist(), "Actual", clr),
            {"name": f"Forecast ({hz} h ahead)", "type": "line", "smooth": True, "showSymbol": False,
             "lineStyle": {"width": 2, "color": "#ffa15a", "type": "dashed"},
             "data": [[xi, yi] for xi, yi in zip(gx, g[fcol].tolist())
                      if not (isinstance(yi, float) and np.isnan(yi))]},
        ],
    }
    st_echarts(options=opt, height="420px")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Forecast error over time** (forecast − actual)")
        e = (g[fcol] - g[ocol]).tolist()
        opt = {
            **base_options(T),
            "xAxis": axis(T, is_time=True),
            "yAxis": yaxis(T, f"Error ({unit})"),
            "series": [{
                "type": "bar", "data": [
                    {"value": v, "itemStyle": {"color": PARAMS["Temperature"][2] if (v or 0) >= 0 else T["err_neg"]}}
                    for v in e],
                "itemStyle": {"borderRadius": [3, 3, 0, 0]},
            }],
        }
        st_echarts(options=opt, height="280px")
    with c2:
        st.markdown("**Forecast vs actual scatter**")
        pts = [[a, b] for a, b in zip(g[ocol].tolist(), g[fcol].tolist())
               if not (np.isnan(a) or np.isnan(b))]
        lo = float(np.nanmin([g[ocol].min(), g[fcol].min()]))
        hi = float(np.nanmax([g[ocol].max(), g[fcol].max()]))
        opt = {
            **base_options(T),
            "tooltip": tooltip(T, "item"),
            "xAxis": {**yaxis(T, "Actual"), "min": lo, "max": hi, "scale": True},
            "yAxis": {**yaxis(T, "Forecast"), "min": lo, "max": hi, "scale": True},
            "series": [
                {"type": "scatter", "symbolSize": 8,
                 "itemStyle": {"color": clr, "opacity": .8}, "data": pts},
                {"type": "line", "data": [[lo, lo], [hi, hi]], "showSymbol": False,
                 "lineStyle": {"color": T["perfect_line"], "type": "dotted"},
                 "tooltip": {"show": False}},
            ],
        }
        st_echarts(options=opt, height="280px")


def _tab_accuracy(T, pairs_f, pairs_hz, hz, rain_thr):
    if pairs_hz.empty:
        st.info("Not enough matched pairs to compute metrics yet.")
        return
    st.caption("Metrics computed with Owner C's evaluation engine (`database/weather_db.py`).")
    em = wdb.error_metrics(pairs_hz)
    st.subheader(f"Error metrics · {hz} h lead time · {int(em['n'].max())} pairs")
    cols = st.columns(len(em))
    for i, r in enumerate(em.itertuples(index=False)):
        cols[i].metric(r.Variable, f"MAE {r.MAE:.2f}", f"RMSE {r.RMSE:.2f}", delta_color="off")

    by_lead = wdb.error_metrics(pairs_f, by_lead_time=True)
    if not by_lead.empty:
        st.markdown("**MAE by forecast lead time**")
        colours = {"Temperature (°C)": PARAMS["Temperature"][2],
                   "Humidity (%)": PARAMS["Humidity"][2],
                   "Wind Speed (km/h)": PARAMS["Wind speed"][2]}
        series = []
        leads = sorted(by_lead["Lead (h)"].unique())
        for var, s in by_lead.groupby("Variable"):
            m = dict(zip(s["Lead (h)"], s.MAE))
            series.append({
                "name": var, "type": "line", "smooth": True,
                "symbolSize": 7, "lineStyle": {"width": 2.5, "color": colours.get(var)},
                "itemStyle": {"color": colours.get(var)},
                "data": [round(m[L], 3) if L in m and not np.isnan(m[L]) else None for L in leads],
            })
        opt = {**base_options(T),
               "xAxis": {**axis(T, "Lead time (h)"), "data": [str(L) for L in leads]},
               "yAxis": yaxis(T, "MAE"),
               "series": series}
        st_echarts(options=opt, height="320px")
        st.dataframe(by_lead, use_container_width=True, hide_index=True)

    st.subheader(f"Rain confusion matrix · {hz} h lead time · threshold {rain_thr} mm")
    cm = wdb.rain_confusion_matrix(pairs_hz, threshold_mm=rain_thr)
    cmdf = wdb.confusion_matrix_df(cm)
    data = [[xi, yi, int(cmdf.loc[idx, col])]
            for yi, idx in enumerate(cmdf.index) for xi, col in enumerate(cmdf.columns)]
    vmax = max(1, int(cmdf.values.max()))
    if T.get("heat_adaptive"):  # dark mode: per-cell text colour so light cells stay readable
        data = [{"value": d, "label": {"color": _label_colour(d[2] / vmax, T)}} for d in data]
    opt = {
        **base_options(T),
        "grid": {"left": CM_LEFT, "right": 10, "top": CM_TOP, "bottom": CM_BOTTOM,
                 "containLabel": False},
        "tooltip": tooltip(T, "item", position="top"),
        "xAxis": {**axis(T), "data": list(cmdf.columns), "splitArea": {"show": True}},
        "yAxis": {**axis(T), "data": list(cmdf.index), "splitArea": {"show": True}},
        "visualMap": {"min": 0, "max": vmax, "calculable": False,
                      "orient": "horizontal", "left": "center", "bottom": 0,
                      "inRange": {"color": T["heat"]},
                      "textStyle": {"color": T["muted"]}, "show": False},
        "series": [{
            "type": "heatmap", "data": data,
            "label": {"show": True, "color": T["heat_label"], "fontSize": 14, "fontWeight": "bold"},
            "itemStyle": {"borderColor": T["heat_border"], "borderWidth": 2, "borderRadius": 6},
        }],
    }
    a, b = st.columns([3, 2], gap="medium")
    with a:
        st_echarts(options=opt, height=f"{CM_H}px")
    acc = cm["Accuracy"]
    metrics = [
        ("Accuracy", fmt(acc * 100 if acc is not None else None, 1) + " %"),
        ("Precision", fmt(cm["Precision"])),
        ("Recall (POD)", fmt(cm["Recall (POD)"])),
        ("False Alarm Ratio", fmt(cm["False Alarm Ratio"])),
    ]
    # 2x2 grid: top row lines up with the "Predicted DRY" row, bottom row with "Predicted RAIN"
    cards = "".join(glass(f'<h4>{label}</h4><div class="big">{value}</div>', "cm") for label, value in metrics)
    with b:
        st.markdown(f'<div class="cm-grid" style="height:{CM_PLOT_H}px;margin-top:{CM_TOP}px;">{cards}</div>',
                    unsafe_allow_html=True)


def _tab_export(obs_f, pairs_f):
    st.subheader("Historical observations")
    st.dataframe(obs_f.sort_values("obs_time", ascending=False), use_container_width=True, hide_index=True)
    st.download_button("⬇️ Export observations (CSV)", obs_f.to_csv(index=False).encode(),
                       "observations.csv", "text/csv")
    if not pairs_f.empty:
        st.download_button("⬇️ Export forecast-vs-actual (CSV)", pairs_f.to_csv(index=False).encode(),
                           "forecast_vs_actual.csv", "text/csv")
        st.download_button("⬇️ Export error metrics by lead time (CSV)",
                           wdb.error_metrics(pairs_f, by_lead_time=True).to_csv(index=False).encode(),
                           "error_metrics.csv", "text/csv")


def render_tabs(T, obs, obs_f, pairs_f, pairs_hz, hz, rain_thr):
    t1, t2, t3, t4 = st.tabs(["📍 Current", "📈 Actual vs Forecast", "🎯 Accuracy", "💾 Data & Export"])
    with t1:
        _tab_current(T, obs)
    with t2:
        _tab_actual_vs_forecast(T, pairs_hz, hz)
    with t3:
        _tab_accuracy(T, pairs_f, pairs_hz, hz, rain_thr)
    with t4:
        _tab_export(obs_f, pairs_f)
