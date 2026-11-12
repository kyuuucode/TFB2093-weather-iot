"""Dark / light colour tokens and the CSS built from them."""

THEME = {
    "dark": {
        "bg": "radial-gradient(1300px 800px at 12% -5%, #17334f 0%, #0d1b2a 48%, #0a1220 100%)",
        "sidebar": "linear-gradient(180deg,#0e1c2e 0%,#0a1220 100%)",
        "card": "linear-gradient(160deg, rgba(255,255,255,.07), rgba(255,255,255,.025))",
        "card_border": "rgba(255,255,255,.10)",
        "text": "#dbe7f5",
        "text_bright": "#eef4fb",
        "muted": "#8fa3b8",
        "axis": "#3a4b5d",
        "grid": "rgba(255,255,255,.07)",
        "shadow": "0 10px 34px rgba(0,0,0,.35)",
        "tab_idle": "rgba(255,255,255,.05)",
        "tab_active": "rgba(94,200,255,.14)",
        "tooltip_bg": "#101a26",
        "tooltip_border": "rgba(255,255,255,.15)",
        "heat": ["#0e2233", "#5ec8ff", "#c9e9ff"],
        "heat_border": "#0d1b2a",
        "heat_label": "#eef4fb",
        "perfect_line": "rgba(255,255,255,.35)",
        "err_neg": "#5ec8ff",
        "input_bg": "rgba(255,255,255,.06)",
        "input_border": "rgba(255,255,255,.14)",
        "input_text": "#dbe7f5",
        "zoom_bg": "rgba(255,255,255,.05)",
        "day_n": "#a8bccf",
        "note_bg": "#14263a",
        "note_text": "#dbe7f5",
        "accent": "#5ec8ff",
        "heat_adaptive": True,
    },
    "light": {
        "bg": "radial-gradient(1300px 800px at 12% -5%, #ffffff 0%, #eef3f8 45%, #dde7f0 100%)",
        "sidebar": "linear-gradient(180deg,#ffffff 0%,#eef3f8 100%)",
        "card": "linear-gradient(160deg, rgba(255,255,255,.72), rgba(255,255,255,.42))",
        "card_border": "rgba(90,120,150,.20)",
        "text": "#33475c",
        "text_bright": "#1c2b3a",
        "muted": "#6d8296",
        "axis": "#c3ccd6",
        "grid": "rgba(90,120,150,.14)",
        "shadow": "0 10px 30px rgba(60,90,120,.12)",
        "tab_idle": "rgba(90,120,150,.10)",
        "tab_active": "rgba(64,150,255,.16)",
        "tooltip_bg": "#ffffff",
        "tooltip_border": "rgba(90,120,150,.25)",
        "heat": ["#eaf2fb", "#8fc4f0", "#2b7fd4"],
        "heat_border": "#ffffff",
        "heat_label": "#1c2b3a",
        "perfect_line": "rgba(60,90,120,.45)",
        "err_neg": "#3d8bd6",
        "input_bg": "rgba(255,255,255,.65)",
        "input_border": "rgba(90,120,150,.22)",
        "input_text": "#33475c",
        "zoom_bg": "rgba(90,120,150,.10)",
        "day_n": "#6d8296",
        "note_bg": "rgba(28,131,225,.10)",
        "note_text": "#1c2b3a",
        "accent": "#2b7fd4",
        "heat_adaptive": False,
    },
}


def get_theme(mode: str) -> dict:
    return THEME[mode]


def _base_css(T):
    return f"""
<style>
.stApp {{background: {T['bg']} !important;}}
.stApp, .stApp p, .stApp span, .stApp label {{color:{T['text']};}}
.block-container {{padding-top:1.6rem;}}
h1, h2, h3 {{color:{T['text_bright']} !important; letter-spacing:.3px;}}
/* glass cards: SOFT background, readable text */
.glass {{
  background:{T['card']};
  border:1px solid {T['card_border']}; border-radius:22px;
  padding:18px 22px; backdrop-filter:blur(14px); box-shadow:{T['shadow']};
}}
.glass .big {{font-size:2.4rem; font-weight:800; line-height:1.05; color:{T['text_bright']};}}
.glass .unit {{font-size:1rem; color:{T['muted']};}}
.glass .sub {{color:{T['muted']}; font-size:.8rem; margin-top:2px;}}
.glass h4 {{color:{T['text']}; margin:0 0 6px 0; font-size:.92rem; font-weight:600;}}
/* right side of the hero: one grid so KPI cards, Next forecast and the reminder line up
   exactly with the weather / sun cards (184 + 10 + 34 + 10 + 34 = 272px) */
.hero-grid {{display:grid; grid-template-columns:repeat(4,1fr); grid-template-rows:184px 34px 34px;
  gap:10px 16px; height:272px;}}
.glass.kpi {{height:100%; box-sizing:border-box; overflow:hidden; padding:14px 22px;
  display:flex; flex-direction:column; justify-content:center;}}
.glass.kpi .big {{font-size:2.8rem;}}
.glass.kpi .unit {{font-size:1.25rem;}}
.glass.kpi .sub {{font-size:.95rem; margin-top:4px;}}
.glass.kpi h4 {{font-size:1.1rem; margin-bottom:10px;}}
.note {{grid-column:1 / -1; box-sizing:border-box; height:34px; padding:0 16px; border-radius:10px;
  background:{T['note_bg']}; color:{T['note_text']}; font-size:.9rem;
  display:flex; align-items:center; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}}
.note b {{font-weight:700;}}
/* hero cards: weather + sun times (same size, same design) */
.glass.hero {{height:272px; box-sizing:border-box; overflow:hidden; display:flex; flex-direction:column; justify-content:center;}}
.hero-emoji {{font-size:4rem; line-height:1.1;}}
.hero-temp {{font-size:3.3rem; font-weight:800; line-height:1.05; color:{T['text_bright']};}}
.hero-unit {{font-size:1.2rem; font-weight:600; color:{T['muted']};}}
.hero-sub {{color:{T['muted']}; font-size:.92rem; margin-top:5px;}}
.hero-cond {{font-size:1.4rem; font-weight:700; color:{T['text_bright']}; margin-top:10px;}}
.sun-row {{display:flex; justify-content:space-between; align-items:center; margin-top:8px; font-size:.98rem;}}
.sun-row .k {{color:{T['muted']};}}
.sun-row .v {{font-weight:700; color:{T['text_bright']};}}
/* confusion-matrix metrics: 2x2 grid that matches the heatmap's plot height */
.cm-grid {{display:grid; grid-template-columns:1fr 1fr; grid-template-rows:1fr 1fr; gap:10px 14px;}}
.glass.cm {{box-sizing:border-box; overflow:hidden; padding:12px 20px;
  display:flex; flex-direction:column; justify-content:center;}}
.glass.cm h4 {{font-size:1rem; margin-bottom:8px;}}
.glass.cm .big {{font-size:2.3rem;}}
div[data-testid="stMetric"]{{
  background:{T['card']}; border:1px solid {T['card_border']};
  border-radius:18px; padding:15px 18px; backdrop-filter:blur(12px); box-shadow:{T['shadow']};}}
div[data-testid="stMetric"] label {{color:{T['muted']} !important;}}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{color:{T['text_bright']} !important; font-weight:700;}}
section[data-testid="stSidebar"]{{
  background:{T['sidebar']}; border-right:1px solid {T['card_border']};}}
section[data-testid="stSidebar"] * {{color:{T['text']} !important;}}
/* NOTE: header is NOT hidden, so the sidebar collapse arrow stays visible */
.stTabs [data-baseweb="tab-list"] {{gap:6px; border-bottom:1px solid {T['card_border']};}}
.stTabs [data-baseweb="tab"] {{
  background:{T['tab_idle']}; border-radius:12px 12px 0 0; padding:8px 18px; color:{T['muted']};}}
.stTabs [aria-selected="true"] {{background:{T['tab_active']}; color:{T['text_bright']} !important;}}
.day-card{{
  background:{T['card']}; border:1px solid {T['card_border']}; border-radius:16px;
  padding:12px 8px; text-align:center; backdrop-filter:blur(10px); box-shadow:{T['shadow']};}}
.day-card .d{{font-size:.74rem; color:{T['muted']};}}
.day-card .t{{font-size:1.02rem; font-weight:700; color:{T['text_bright']};}}
.day-card .n{{font-size:.72rem; color:{T['day_n']};}}
/* inputs: toned down, readable in both modes */
div[data-testid="stDateInput"] input, div[data-testid="stSelectbox"] > div > div,
div[data-testid="stSlider"] > div > div > div {{
  background:{T['input_bg']} !important; color:{T['input_text']} !important;
  border-color:{T['input_border']} !important;}}
div[data-testid="stDateInput"] input {{color:{T['input_text']} !important;}}
div[data-baseweb="select"] > div {{
  background:{T['input_bg']} !important; border-color:{T['input_border']} !important;}}
div[data-baseweb="select"] span {{color:{T['input_text']} !important;}}
div[data-testid="stRadio"] label {{color:{T['text']} !important;}}
div[data-testid="stRadio"] [role="radiogroup"] {{
  background:{T['input_bg']}; border:1px solid {T['input_border']}; border-radius:12px; padding:4px 8px;}}
.stDownloadButton button {{border-radius:12px;}}
</style>
"""


def _dark_css(T):
    """Dark-mode-only colour fixes (sizes/spacing follow light mode)."""
    return f"""
<style>
/* white Streamlit top bar -> transparent */
header[data-testid="stHeader"] {{background:transparent !important;}}
header[data-testid="stHeader"] * {{color:{T['muted']} !important;}}

/* date range: one solid dark colour on every nested layer, so no white shows through */
div[data-testid="stDateInput"] > div:not([data-testid="stWidgetLabel"]),
div[data-testid="stDateInput"] > div:not([data-testid="stWidgetLabel"]) div,
div[data-testid="stDateInput"] div[data-baseweb="input"],
div[data-testid="stDateInput"] div[data-baseweb="input"] div,
div[data-testid="stDateInput"] div[data-baseweb="base-input"],
div[data-testid="stDateInput"] [data-testid="stDateInputField"],
div[data-testid="stDateInput"] input {{
  background:#1a2838 !important; background-color:#1a2838 !important;
  color:{T['input_text']} !important; -webkit-text-fill-color:{T['input_text']} !important;
  border-color:{T['input_border']} !important;}}
div[data-testid="stDateInput"] svg {{fill:{T['muted']} !important; color:{T['muted']} !important;}}

/* buttons (Refresh data, exports) */
.stButton > button, .stDownloadButton > button {{
  background:{T['input_bg']} !important; border-color:{T['input_border']} !important;
  color:{T['input_text']} !important;}}
.stButton > button:hover, .stDownloadButton > button:hover {{border-color:#5ec8ff !important;}}
.stButton > button p, .stDownloadButton > button p {{color:inherit !important;}}

/* st.info / st.warning: dark background, light text */
div[data-testid="stAlert"], div[data-testid="stAlert"] div[data-baseweb="notification"],
div[data-testid="stAlertContainer"] {{background:#14263a !important;}}
div[data-testid="stAlert"] * {{color:{T['text']} !important;}}

/* code chips (DB: weather.db, weather_db.py) */
code, section[data-testid="stSidebar"] code {{
  background:rgba(94,200,255,.12) !important; color:#9fd8ff !important;}}

/* RMSE pill under the MAE value: remove the white fill, keep readable text */
div[data-testid="stMetricDelta"], div[data-testid="stMetricDelta"] * {{
  background:transparent !important; color:#b8cde0 !important; fill:#b8cde0 !important;}}
</style>
"""


def build_css(mode: str) -> str:
    """All CSS for the given mode ('dark' | 'light')."""
    T = THEME[mode]
    return _base_css(T) + (_dark_css(T) if mode == "dark" else "")
