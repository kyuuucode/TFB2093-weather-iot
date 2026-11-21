"""Injects assets/scroll_lock.js so the page doesn't jump to the top on every rerun."""
from pathlib import Path

import streamlit.components.v1 as components

_JS = Path(__file__).parent / "assets" / "scroll_lock.js"


def keep_scroll_position():
    components.html(f"<script>{_JS.read_text(encoding='utf-8')}</script>", height=0)
