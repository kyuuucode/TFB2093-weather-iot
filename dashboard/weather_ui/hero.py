"""Hero section: weather card, Sun Times card, KPI cards, Next forecast + reminder."""
import numpy as np
import pandas as pd
import streamlit as st

from .helpers import fmt, glass
from .sun import get_sun_times


def weather_condition(rain, hum):
    """Emoji + label from the latest rainfall / humidity."""
    if rain >= 5:
        return "⛈️", "Thunder Storm"
    if rain >= 0.5:
        return "🌧️", "Rainy"
    if rain > 0:
        return "🌦️", "Light Showers"
    if hum >= 95:
        return "🌫️", "Misty"
    if hum >= 80:
        return "☁️", "Cloudy"
    return "🌤️", "Partly Cloudy"


def feels_like(temp, hum):
    """Simplified apparent temperature."""
    if temp < 20:
        return temp
    return temp + 0.33 * (hum / 100 * 6.105) * np.exp(temp / 16)


def pick_snapshot(obs, d1):
    """Last observation on or before the END of the selected date range (falls back to latest)."""
    sel = obs[obs["obs_time"].dt.date <= d1]
    if sel.empty:
        sel = obs
    last = sel.iloc[-1]
    prev = sel.iloc[-2] if len(sel) > 1 else last
    is_latest = last["obs_time"] == obs["obs_time"].iloc[-1]
    return last, prev, is_latest


def reminder_html(obs, nxt, sel_day, is_latest, rain_thr):
    """Umbrella / sunny-day line. Live forecast for the latest day, observed summary for past days."""
    if is_latest:
        if nxt.empty:
            return None
        win = nxt[nxt["target_time"].dt.date == sel_day]
        if len(win) < 4:  # late in the day -> look at the next 12 hours instead
            win, scope = nxt.head(12), "in the next 12 hours"
        else:
            scope = "today"
        w_prob = win["rain_probability_pct"].max()
        w_prob = 0 if pd.isna(w_prob) else float(w_prob)
        w_rain = win[win["rainfall_mm"] >= rain_thr]
        tmax = win["temperature_c"].max()
        if not w_rain.empty or w_prob >= 60:
            ref = w_rain if not w_rain.empty else win[win["rain_probability_pct"] >= 60]
            first_t = ref.iloc[0]["target_time"]
            peak = win["rainfall_mm"].max()
            return (f"☔ <b>Don't forget to bring your umbrella!</b> Rain is expected {scope}, "
                    f"starting around {first_t:%I:%M %p} (up to {w_prob:.0f}% chance, peak {peak:.1f} mm/h).")
        if w_prob >= 30:
            return (f"🌦️ <b>Small chance of showers {scope}</b> (up to {w_prob:.0f}%). "
                    f"You probably won't need it, but keep a small umbrella handy just in case.")
        head = "Today is gonna be a sunny day!" if scope == "today" else "Clear skies ahead!"
        return (f"☀️ <b>{head}</b> No rain expected {scope}, with highs around {tmax:.0f} °C. "
                f"Enjoy it, and remember to stay hydrated.")

    d_obs = obs[obs["obs_time"].dt.date == sel_day]
    rr = d_obs["rainfall_mm"].fillna(0)
    total, peak, tmax = float(rr.sum()), float(rr.max()), d_obs["temperature_c"].max()
    wet = d_obs[rr >= rain_thr]
    if not wet.empty:
        return (f"☔ <b>It rained on {sel_day:%d %b}:</b> {total:.1f} mm in total, from "
                f"{wet['obs_time'].iloc[0]:%I:%M %p} to {wet['obs_time'].iloc[-1]:%I:%M %p} "
                f"(peak {peak:.1f} mm/h).")
    if total > 0:
        return (f"🌦️ <b>Only light showers on {sel_day:%d %b}</b> ({total:.1f} mm in total), "
                f"highs of {tmax:.0f} °C.")
    return f"☀️ <b>{sel_day:%d %b} was a dry day</b> with no rain recorded, highs of {tmax:.0f} °C."


def render_hero(T, obs, fc, d1, rain_thr, db_path):
    """Render the hero. Returns (sel_day, accent) for the multi-day strip."""
    last, prev, is_latest = pick_snapshot(obs, d1)
    sel_day = last["obs_time"].date()
    tag = "(Latest)" if is_latest else "(Selected date)"
    accent = T["accent"]

    rain = last.rainfall_mm or 0
    hum = last.humidity_pct or 0
    emoji, cond = weather_condition(rain, hum)
    fl = feels_like(last.temperature_c, hum)

    sunrise, sunset, sun_src = get_sun_times(db_path, sel_day)
    day_len = sunset - sunrise
    day_h, day_m = int(day_len.total_seconds() // 3600), int(day_len.total_seconds() % 3600 // 60)

    hero_l, hero_r = st.columns([1.0, 2.2], gap="large")
    with hero_l:
        w_col, s_col = st.columns(2, gap="small")
        with w_col:
            st.markdown(glass(f"""
                <div class="hero-emoji">{emoji}</div>
                <div class="hero-temp">{last.temperature_c:.1f}<span class="hero-unit"> °C</span></div>
                <div class="hero-sub">🌡️ Feels like {fl:.1f} °C</div>
                <div class="hero-cond">{cond}</div>
                <div class="hero-sub">🕘 {last['obs_time']:%d %b %Y · %H:%M} <span style="color:{accent};font-weight:700;">{tag}</span></div>
            """, "hero"), unsafe_allow_html=True)
        with s_col:
            st.markdown(glass(f"""
                <div class="hero-emoji">🌅</div>
                <div class="hero-cond" style="margin-top:2px;">Sun Times</div>
                <div class="sun-row"><span class="k">🌅 Sunrise</span><span class="v">{sunrise:%I:%M %p}</span></div>
                <div class="sun-row"><span class="k">🌇 Sunset</span><span class="v">{sunset:%I:%M %p}</span></div>
                <div class="sun-row"><span class="k">⏳ Day length</span><span class="v">{day_h}h {day_m:02d}m</span></div>
                <div class="hero-sub">📅 {sel_day:%d %b %Y} · {sun_src}</div>
            """, "hero"), unsafe_allow_html=True)

    with hero_r:
        def delta(col, d=1):
            if pd.isna(last[col]) or pd.isna(prev[col]):
                return None
            return f"{last[col] - prev[col]:+.{d}f}"

        nxt = (fc[fc["target_time"] > last["obs_time"]]
               .sort_values(["target_time", "lead_time_hours"])
               .drop_duplicates("target_time"))
        prob_now = nxt.iloc[0]["rain_probability_pct"] if not nxt.empty else np.nan

        cards = [
            glass(f"""
            <h4>💨 Wind Status</h4>
            <div class="big">{last.wind_speed_kmh:.1f}</div>
            <div class="unit">km/h</div>
            <div class="sub">Δ {delta('wind_speed_kmh') or '–'} vs prev. hour</div>
            """, "kpi"),
            glass(f"""
            <h4>💧 Humidity</h4>
            <div class="big">{last.humidity_pct:.0f}</div>
            <div class="unit">%</div>
            <div class="sub">Δ {delta('humidity_pct', 0) or '–'} vs prev. hour</div>
            """, "kpi"),
            glass(f"""
            <h4>☔ Rain Chance</h4>
            <div class="big">{fmt(prob_now, 0) if pd.notna(prob_now) else '–'}</div>
            <div class="unit">%</div>
            <div class="sub">next-hour forecast</div>
            """, "kpi"),
            glass(f"""
            <h4>🌧️ Rainfall</h4>
            <div class="big">{last.rainfall_mm:.1f}</div>
            <div class="unit">mm</div>
            <div class="sub">Δ {delta('rainfall_mm') or '–'} vs prev. hour</div>
            """, "kpi"),
        ]

        if not nxt.empty:
            n = nxt.iloc[0]
            prob = (f" · {n.rain_probability_pct:.0f}% chance of rain"
                    if pd.notna(n.rain_probability_pct) else "")
            cards.append('<div class="note">'
                         f"<b>Next forecast ({n['target_time']:%d %b %H:%M}):</b> {n.temperature_c:.1f} °C · "
                         f"{n.humidity_pct:.0f}% · {n.rainfall_mm:.1f} mm · {n.wind_speed_kmh:.1f} km/h{prob}"
                         '</div>')

        rem = reminder_html(obs, nxt, sel_day, is_latest, rain_thr)
        if rem:
            cards.append(f'<div class="note">{rem}</div>')

        # one HTML block, no blank lines (a blank line would end the markdown HTML block)
        st.markdown('<div class="hero-grid">' + "\n".join(c.strip() for c in cards) + '</div>',
                    unsafe_allow_html=True)
    return sel_day, accent
