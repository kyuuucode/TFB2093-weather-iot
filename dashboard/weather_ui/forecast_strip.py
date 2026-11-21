"""Multi-day forecast strip: 7-day window around the selected date."""
import streamlit as st


def render_multiday(fc, sel_day, accent):
    st.markdown('<h3 style="margin-top:14px;">📅 Multi-day Forecast</h3>', unsafe_allow_html=True)
    if fc.empty:
        return
    daily = (fc[fc["lead_time_hours"] <= 72]
             .assign(date=fc["target_time"].dt.date)
             .groupby("date")
             .agg(tmax=("temperature_c", "max"), tmin=("temperature_c", "min"),
                  rain=("rainfall_mm", "sum"), prob=("rain_probability_pct", "max")))
    dates = list(daily.index)
    pos = max([i for i, dd in enumerate(dates) if dd <= sel_day], default=0)
    start = min(max(pos - 3, 0), max(len(dates) - 7, 0))
    daily = daily.iloc[start:start + 7]

    cols = st.columns(len(daily))
    for i, (d, r) in enumerate(daily.iterrows()):
        e = "🌧️" if r.rain >= 1 else ("🌦️" if r.rain > 0 else "🌤️")
        border = f'style="border:1px solid {accent};"' if d == sel_day else ""
        cols[i].markdown(f"""
            <div class="day-card" {border}>
              <div class="d">{d.strftime('%a %d %b')}</div>
              <div style="font-size:1.5rem;">{e}</div>
              <div class="t">{r.tmax:.0f}° <span class="n">/ {r.tmin:.0f}°</span></div>
              <div class="n">{r.rain:.1f} mm · {r.prob:.0f}% rain</div>
            </div>""", unsafe_allow_html=True)
