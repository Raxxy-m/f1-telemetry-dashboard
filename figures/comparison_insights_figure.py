import numpy as np
import plotly.graph_objects as go
from fastf1.plotting import get_driver_style
import pandas as pd

from theme import COLORS, apply_standard_hover_layout


def _message_figure(message):
    fig = go.Figure()
    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[
            dict(
                text=message,
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(color=COLORS["text_muted"], size=14),
            )
        ],
        margin=dict(l=10, r=10, t=20, b=10),
    )
    return fig


def _driver_meta(session, driver):
    driver_info = session.get_driver(driver)
    abbr = driver_info["Abbreviation"]
    style = get_driver_style(abbr, style=["color"], session=session)
    return abbr, style["color"]


def _safe_seconds(value):
    return value.total_seconds() if pd.notna(value) else np.nan


def build_cumulative_delta_figure(driver_tel_dict, session):
    if len(driver_tel_dict) != 2:
        return _message_figure("Select exactly 2 drivers to enable cumulative delta.")

    driver_1, driver_2 = list(driver_tel_dict.keys())
    tel_1 = driver_tel_dict[driver_1].sort_values("Distance").copy()
    tel_2 = driver_tel_dict[driver_2].sort_values("Distance").copy()

    max_distance = min(tel_1["Distance"].max(), tel_2["Distance"].max())
    if np.isnan(max_distance) or max_distance <= 0:
        return _message_figure("Telemetry distance data unavailable for delta calculation.")

    distance_axis = np.linspace(0, max_distance, 1400)
    t1 = np.interp(
        distance_axis,
        tel_1["Distance"],
        tel_1["Time"].dt.total_seconds(),
    )
    t2 = np.interp(
        distance_axis,
        tel_2["Distance"],
        tel_2["Time"].dt.total_seconds(),
    )

    delta = t2 - t1
    if np.all(np.isnan(delta)):
        return _message_figure("Delta could not be computed for the selected laps.")

    abbr_1, color_1 = _driver_meta(session, driver_1)
    abbr_2, color_2 = _driver_meta(session, driver_2)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=distance_axis,
            y=delta,
            mode="lines",
            line=dict(color=color_1, width=2.8),
            name=f"{abbr_1} Ahead",
            hovertemplate=(
                "Distance: %{x:.0f} m<br>"
                f"Delta ({abbr_2} - {abbr_1}): "
                "%{y:+.3f}s<extra></extra>"
            ),
        )
    )

    positive = np.where(delta >= 0, delta, np.nan)
    negative = np.where(delta < 0, delta, np.nan)

    fig.add_trace(
        go.Scatter(
            x=distance_axis,
            y=positive,
            mode="lines",
            line=dict(width=0),
            fill="tozeroy",
            fillcolor="rgba(0, 210, 190, 0.18)",
            name=f"{abbr_1} Gain",
            hoverinfo="skip",
            showlegend=False,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=distance_axis,
            y=negative,
            mode="lines",
            line=dict(width=0),
            fill="tozeroy",
            fillcolor="rgba(255, 24, 1, 0.18)",
            name=f"{abbr_2} Gain",
            hoverinfo="skip",
            showlegend=False,
        )
    )

    max_idx = int(np.nanargmax(delta))
    min_idx = int(np.nanargmin(delta))

    fig.add_annotation(
        x=distance_axis[max_idx],
        y=delta[max_idx],
        text=f"{abbr_1} max +{delta[max_idx]:.3f}s",
        showarrow=True,
        arrowhead=2,
        ax=20,
        ay=-30,
        font=dict(size=10, color=COLORS["text_secondary"]),
        arrowcolor=color_1,
    )

    fig.add_annotation(
        x=distance_axis[min_idx],
        y=delta[min_idx],
        text=f"{abbr_2} max +{abs(delta[min_idx]):.3f}s",
        showarrow=True,
        arrowhead=2,
        ax=20,
        ay=30,
        font=dict(size=10, color=COLORS["text_secondary"]),
        arrowcolor=color_2,
    )

    fig.add_hline(
        y=0,
        line_width=1,
        line_dash="dot",
        line_color=COLORS["border_strong"],
    )

    fig = apply_standard_hover_layout(fig)
    fig.update_layout(
        margin=dict(l=52, r=16, t=38, b=40),
        height=360,
        legend=dict(orientation="h", y=1.02, x=0),
    )
    fig.update_xaxes(title_text="Distance (m)")
    fig.update_yaxes(title_text=f"Delta ({abbr_2} - {abbr_1}) [s]")
    return fig


def build_sector_delta_figure(fastest_laps, session):
    if len(fastest_laps) != 2:
        return _message_figure("Select exactly 2 drivers to compare sector deltas.")

    driver_1, driver_2 = list(fastest_laps.keys())
    lap_1 = fastest_laps[driver_1]
    lap_2 = fastest_laps[driver_2]

    abbr_1, color_1 = _driver_meta(session, driver_1)
    abbr_2, color_2 = _driver_meta(session, driver_2)

    sector_labels = ["Sector 1", "Sector 2", "Sector 3"]
    sector_1 = [
        _safe_seconds(lap_1["Sector1Time"]),
        _safe_seconds(lap_1["Sector2Time"]),
        _safe_seconds(lap_1["Sector3Time"]),
    ]
    sector_2 = [
        _safe_seconds(lap_2["Sector1Time"]),
        _safe_seconds(lap_2["Sector2Time"]),
        _safe_seconds(lap_2["Sector3Time"]),
    ]

    deltas = np.array(sector_2) - np.array(sector_1)
    colors = [color_1 if val >= 0 else color_2 for val in deltas]
    labels = [f"{val:+.3f}s" for val in deltas]

    fig = go.Figure(
        go.Bar(
            y=sector_labels,
            x=deltas,
            orientation="h",
            text=labels,
            textposition="auto",
            marker=dict(color=colors),
            hovertemplate=(
                "%{y}<br>"
                f"{abbr_2} - {abbr_1}: "
                "%{x:+.3f}s<extra></extra>"
            ),
        )
    )

    finite_deltas = deltas[np.isfinite(deltas)]
    if finite_deltas.size == 0:
        return _message_figure("Sector delta unavailable for the selected laps.")
    max_abs = max(abs(finite_deltas.min()), abs(finite_deltas.max()), 0.08)
    fig.add_vline(
        x=0,
        line_width=1,
        line_dash="dot",
        line_color=COLORS["border_strong"],
    )

    fig = apply_standard_hover_layout(fig)
    fig.update_layout(
        margin=dict(l=86, r=28, t=38, b=34),
        height=360,
        showlegend=False,
    )
    fig.update_xaxes(
        title_text=f"Delta (s) | + = {abbr_1} faster",
        range=[-max_abs * 1.25, max_abs * 1.25],
    )
    fig.update_yaxes(autorange="reversed", automargin=True)
    return fig


def build_speed_profile_figure(driver_tel_dict, session):
    if not driver_tel_dict:
        return _message_figure("Select at least one driver to render speed distribution.")

    fig = go.Figure()

    for driver, tel in driver_tel_dict.items():
        abbr, color = _driver_meta(session, driver)
        speed_values = tel["Speed"].dropna()
        if speed_values.empty:
            continue

        fig.add_trace(
            go.Histogram(
                x=speed_values,
                nbinsx=26,
                histnorm="percent",
                opacity=0.52,
                marker=dict(color=color),
                name=abbr,
                hovertemplate=(
                    f"{abbr}<br>"
                    "Speed bin: %{x:.0f} km/h<br>"
                    "Share: %{y:.2f}%<extra></extra>"
                ),
            )
        )

        fig.add_vline(
            x=float(speed_values.mean()),
            line_color=color,
            line_width=1.6,
            line_dash="dot",
        )

    fig = apply_standard_hover_layout(fig)
    fig.update_layout(
        barmode="overlay",
        margin=dict(l=52, r=16, t=40, b=46),
        height=320,
    )
    fig.update_xaxes(title_text="Speed (km/h)")
    fig.update_yaxes(title_text="Lap Distance Share (%)")
    return fig
