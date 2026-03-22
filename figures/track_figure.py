import numpy as np
import plotly.graph_objects as go

from theme import COLORS

def adjust_color_brightness(hex_color, factor=0.8):
    hex_color = hex_color.lstrip("#")
    r, g, b = [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]

    r = int(max(0, min(255, r * factor)))
    g = int(max(0, min(255, g * factor)))
    b = int(max(0, min(255, b * factor)))

    return f"#{r:02x}{g:02x}{b:02x}"


def _driver_color(session, driver, fallback):
    if session is None or driver is None:
        return fallback
    info = session.get_driver(driver)
    color = str(info.get("TeamColor", "")).strip()
    if not color:
        return fallback
    return color if color.startswith("#") else f"#{color}"


def _segment_points(x_vals, y_vals, segment_mask):
    if len(x_vals) < 2:
        return [], []

    seg_x = []
    seg_y = []
    for idx in range(len(x_vals) - 1):
        if not segment_mask[idx]:
            continue
        x0 = x_vals[idx]
        y0 = y_vals[idx]
        x1 = x_vals[idx + 1]
        y1 = y_vals[idx + 1]
        if not (np.isfinite(x0) and np.isfinite(y0) and np.isfinite(x1) and np.isfinite(y1)):
            continue
        seg_x.extend([x0, x1, None])
        seg_y.extend([y0, y1, None])
    return seg_x, seg_y


def build_single_driver_track(tel):
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=tel["X"],
            y=tel["Y"],
            mode="lines",
            line=dict(color="rgba(255,255,255,0.3)", width=6),
            showlegend=False
        )
    )

    fig.update_layout(
        title=dict(text="Track Layout", x=0.5, xanchor="center"),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, scaleanchor="x", scaleratio=1),
        margin=dict(l=12, r=12, t=66, b=18),
    )

    return fig


def build_binary_delta_track(delta_tel, driver1, driver2, faster_index, session):
    fig = go.Figure()
    required_columns = {"X", "Y", "Delta"}
    if delta_tel is None or delta_tel.empty or not required_columns.issubset(set(delta_tel.columns)):
        return build_multi_driver_message()

    color1 = _driver_color(session, driver1, COLORS["telemetry_1"])
    color2 = _driver_color(session, driver2, COLORS["telemetry_2"])

    # Handle teammates
    if color1 == color2:
        color1 = adjust_color_brightness(color1, 1.2)
        color2 = adjust_color_brightness(color2, 0.75)

    if faster_index == 0:
        faster_driver = driver1
        slower_driver = driver2
        faster_color = color1
        slower_color = color2
    else:
        faster_driver = driver2
        slower_driver = driver1
        faster_color = color2
        slower_color = color1

    # Base outline
    fig.add_trace(
        go.Scatter(
            x=delta_tel["X"],
            y=delta_tel["Y"],
            mode="lines",
            line=dict(color="rgba(255,255,255,0.08)", width=10),
            showlegend=False,
            hoverinfo="skip"
        )
    )

    x_values = np.asarray(delta_tel["X"], dtype=float)
    y_values = np.asarray(delta_tel["Y"], dtype=float)
    delta_values = np.asarray(delta_tel["Delta"], dtype=float)

    fast_mask = np.zeros(len(delta_values), dtype=bool)
    slow_mask = np.zeros(len(delta_values), dtype=bool)
    if len(delta_values) > 1:
        segment_valid = (
            np.isfinite(x_values[:-1])
            & np.isfinite(y_values[:-1])
            & np.isfinite(x_values[1:])
            & np.isfinite(y_values[1:])
            & np.isfinite(delta_values[:-1])
        )
        fast_mask[:-1] = segment_valid & (delta_values[:-1] > 0)
        slow_mask[:-1] = segment_valid & (delta_values[:-1] <= 0)

    fast_x, fast_y = _segment_points(x_values, y_values, fast_mask)
    slow_x, slow_y = _segment_points(x_values, y_values, slow_mask)

    if fast_x:
        fig.add_trace(
            go.Scatter(
                x=fast_x,
                y=fast_y,
                mode="lines",
                line=dict(width=5, color=faster_color),
                showlegend=False,
                hoverinfo="skip",
            )
        )

    if slow_x:
        fig.add_trace(
            go.Scatter(
                x=slow_x,
                y=slow_y,
                mode="lines",
                line=dict(width=5, color=slower_color),
                showlegend=False,
                hoverinfo="skip",
            )
        )

    # Legend
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="lines",
            line=dict(color=faster_color, width=6),
            name=f"{faster_driver} Faster"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="lines",
            line=dict(color=slower_color, width=6),
            name=f"{slower_driver} Faster"
        )
    )

    fig.update_layout(
        title=dict(
            text=f"{faster_driver} vs {slower_driver} | Faster by track segment",
            x=0.5,
            xanchor="center",
            y=0.96,
            yanchor="top",
        ),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, scaleanchor="x", scaleratio=1),
        margin=dict(l=12, r=12, t=72, b=18),
    )

    return fig


def build_multi_driver_message():
    fig = go.Figure()

    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[
            dict(
                text="Track comparison supports exactly 2 drivers.<br>"
                     "Please select two drivers to enable delta view.",
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(color=COLORS['text_muted'], size=16)
            )
        ],
        margin=dict(l=10, r=10, t=10, b=10),
    )

    return fig
