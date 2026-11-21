"""Tiny formatting / HTML helpers."""
import numpy as np


def fmt(x, d=2):
    """Format a number, or an en dash for None / NaN."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    return f"{x:.{d}f}"


def glass(inner, cls=""):
    """Wrap HTML in a glassmorphism card."""
    return f'<div class="glass {cls}">{inner}</div>'
