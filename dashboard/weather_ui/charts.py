"""Apache ECharts option helpers (colours follow the active theme dict `T`)."""
import numpy as np


def base_options(T):
    return {
        "backgroundColor": "transparent",
        "textStyle": {"color": T["text"]},
        "tooltip": tooltip(T),
        "grid": {"left": 8, "right": 14, "top": 34, "bottom": 8, "containLabel": True},
        "legend": {"textStyle": {"color": T["muted"]}, "top": 0, "icon": "roundRect",
                   "itemWidth": 14, "itemHeight": 8},
    }


def tooltip(T, trigger="axis", **extra):
    return {"trigger": trigger, "backgroundColor": T["tooltip_bg"],
            "borderColor": T["tooltip_border"], "textStyle": {"color": T["text"]}, **extra}


def axis(T, name=None, is_time=False):
    a = {
        "type": "time" if is_time else "category",
        "axisLine": {"lineStyle": {"color": T["axis"]}},
        "axisLabel": {"color": T["muted"]},
        "splitLine": {"show": False},
    }
    if name:
        a["name"] = name
        a["nameTextStyle"] = {"color": T["muted"]}
    return a


def yaxis(T, name=None):
    y = {
        "type": "value",
        "axisLine": {"show": False},
        "axisLabel": {"color": T["muted"]},
        "splitLine": {"lineStyle": {"color": T["grid"]}},
    }
    if name:
        y["name"] = name
        y["nameTextStyle"] = {"color": T["muted"]}
    return y


def area_line(x, y, name, color, width=3):
    return {
        "name": name, "type": "line", "smooth": True, "showSymbol": False,
        "lineStyle": {"width": width, "color": color},
        "areaStyle": {"color": {
            "type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
            "colorStops": [{"offset": 0, "color": color + "55"}, {"offset": 1, "color": color + "00"}],
        }},
        "data": [[xi, yi] for xi, yi in zip(x, y) if not (isinstance(yi, float) and np.isnan(yi))],
    }
