"""Sidebar: theme toggle + filters. Returns the chosen filter values."""
import os
from typing import NamedTuple, Optional

import streamlit as st

from .data import wdb


class Filters(NamedTuple):
    loc: str
    d0: object
    d1: object
    hz: Optional[int]
    rain_thr: float


def render_sidebar(obs_all, pairs_all, db_path) -> Filters:
    with st.sidebar:
        st.markdown("## 🌦️ Weatherly")
        st.caption("Seri Iskandar · TFB2093 IoT")
        st.toggle("☀️ Light mode / 🌙 Dark mode", key="light_mode")
        st.divider()
        if obs_all.empty:
            st.error("No observations in database yet. Keep the ingestion script running.")
            st.stop()

        locations = sorted(obs_all["location"].unique())
        loc = st.selectbox("Location", locations) if len(locations) > 1 else locations[0]
        obs = obs_all[obs_all["location"] == loc]
        pairs = pairs_all[pairs_all["location"] == loc]

        dmin, dmax = obs["obs_time"].min().date(), obs["obs_time"].max().date()
        rng = st.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)
        if isinstance(rng, tuple) and len(rng) == 2:
            d0, d1 = rng
        else:
            d0 = d1 = rng[0] if isinstance(rng, tuple) else rng

        horizons = sorted(int(x) for x in pairs["lead_time_hours"].unique()) if not pairs.empty else []
        if horizons:
            default = (horizons.index(wdb.HEADLINE_LEAD_H)
                       if wdb.HEADLINE_LEAD_H in horizons else len(horizons) - 1)
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
        st.caption(f"🗄️ DB: `{os.path.basename(db_path)}`")
    return Filters(loc, d0, d1, hz, float(rain_thr))
