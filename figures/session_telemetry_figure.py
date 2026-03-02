import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
        margin=dict(l=10, r=10, t=10, b=10),
    )
    return fig


def create_full_session_speed_figure(
    telemetry,
    driver,
    lap_number,
    reference_telemetry=None,
    reference_lap_number=None,
):
    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.42, 0.22, 0.2, 0.16],
    )

    selected_color = COLORS["telemetry_1"]
    reference_color = COLORS["telemetry_3"]

    fig.add_trace(
        go.Scatter(
            x=telemetry["Distance"],
            y=telemetry["Speed"],
            mode="lines",
            name=f"Lap {lap_number}",
            line=dict(color=selected_color, width=2.6),
            hovertemplate="Distance: %{x:.0f} m<br>Speed: %{y:.1f} km/h<extra></extra>",
        ),
        row=1,
        col=1,
    )

    if reference_telemetry is not None and reference_lap_number is not None:
        fig.add_trace(
            go.Scatter(
                x=reference_telemetry["Distance"],
                y=reference_telemetry["Speed"],
                mode="lines",
                name=f"Fastest (Lap {reference_lap_number})",
                line=dict(color=reference_color, width=2.0, dash="dash"),
                hovertemplate="Distance: %{x:.0f} m<br>Speed: %{y:.1f} km/h<extra></extra>",
            ),
            row=1,
            col=1,
        )

    fig.add_trace(
        go.Scatter(
            x=telemetry["Distance"],
            y=telemetry["Throttle"],
            mode="lines",
            line=dict(color=selected_color, width=1.8),
            showlegend=False,
            hovertemplate="Distance: %{x:.0f} m<br>Throttle: %{y:.0f}%<extra></extra>",
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=telemetry["Distance"],
            y=telemetry["Brake"].astype(int) * 100,
            mode="lines",
            fill="tozeroy",
            line=dict(color=selected_color, shape="hv", width=1.2),
            opacity=0.35,
            showlegend=False,
            hovertemplate="Distance: %{x:.0f} m<br>Brake: %{y:.0f}%<extra></extra>",
        ),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=telemetry["Distance"],
            y=telemetry["nGear"],
            mode="lines",
            line=dict(color=selected_color, shape="hv", width=1.8),
            showlegend=False,
            hovertemplate="Distance: %{x:.0f} m<br>Gear: %{y}<extra></extra>",
        ),
        row=4,
        col=1,
    )

    if reference_telemetry is not None:
        fig.add_trace(
            go.Scatter(
                x=reference_telemetry["Distance"],
                y=reference_telemetry["Throttle"],
                mode="lines",
                line=dict(color=reference_color, width=1.4, dash="dash"),
                showlegend=False,
                hoverinfo="skip",
            ),
            row=2,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=reference_telemetry["Distance"],
                y=reference_telemetry["Brake"].astype(int) * 100,
                mode="lines",
                line=dict(color=reference_color, width=1.2, dash="dash", shape="hv"),
                showlegend=False,
                hoverinfo="skip",
            ),
            row=3,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=reference_telemetry["Distance"],
                y=reference_telemetry["nGear"],
                mode="lines",
                line=dict(color=reference_color, width=1.3, dash="dash", shape="hv"),
                showlegend=False,
                hoverinfo="skip",
            ),
            row=4,
            col=1,
        )

    fig = apply_standard_hover_layout(fig)
    fig.update_layout(
        margin=dict(l=52, r=16, t=36, b=35),
        height=760,
        legend=dict(
            orientation="h",
            y=0.995,
            x=0,
            yanchor="top",
            xanchor="left",
            bgcolor="rgba(17, 23, 34, 0.45)",
        ),
    )
    fig.update_yaxes(title_text="Speed (km/h)", row=1, col=1)
    fig.update_yaxes(title_text="Throttle (%)", range=[0, 100], row=2, col=1)
    fig.update_yaxes(title_text="Brake (%)", range=[0, 100], row=3, col=1)
    fig.update_yaxes(title_text="Gear", dtick=1, row=4, col=1)
    fig.update_xaxes(title_text="Distance (m)", row=4, col=1, gridcolor=COLORS["grid"])
    fig.update_yaxes(showgrid=False, row=2, col=1)
    fig.update_yaxes(showgrid=False, row=3, col=1)
    fig.update_yaxes(showgrid=False, row=4, col=1)
    return fig


def create_lap_delta_to_reference_figure(
    telemetry,
    reference_telemetry,
    driver,
    lap_number,
    reference_lap_number,
):
    if reference_telemetry is None:
        return _message_figure("Fastest lap not available for delta comparison.")

    max_distance = min(telemetry["Distance"].max(), reference_telemetry["Distance"].max())
    if np.isnan(max_distance) or max_distance <= 0:
        return _message_figure("Insufficient telemetry for lap delta calculation.")

    distance_axis = np.linspace(0, max_distance, 1200)
    selected_time = np.interp(
        distance_axis,
        telemetry["Distance"],
        telemetry["Time"].dt.total_seconds(),
    )
    reference_time = np.interp(
        distance_axis,
        reference_telemetry["Distance"],
        reference_telemetry["Time"].dt.total_seconds(),
    )

    delta = selected_time - reference_time

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=distance_axis,
            y=delta,
            mode="lines",
            line=dict(color=COLORS["telemetry_1"], width=2.3),
            name=f"Lap {lap_number}",
            hovertemplate=(
                "Distance: %{x:.0f} m<br>"
                f"Delta vs Lap {reference_lap_number}: %{{y:+.3f}}s<extra></extra>"
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=distance_axis,
            y=np.where(delta > 0, delta, np.nan),
            mode="lines",
            line=dict(width=0),
            fill="tozeroy",
            fillcolor="rgba(255, 24, 1, 0.16)",
            hoverinfo="skip",
            showlegend=False,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=distance_axis,
            y=np.where(delta <= 0, delta, np.nan),
            mode="lines",
            line=dict(width=0),
            fill="tozeroy",
            fillcolor="rgba(0, 210, 190, 0.16)",
            hoverinfo="skip",
            showlegend=False,
        )
    )

    fig.add_hline(
        y=0,
        line_width=1,
        line_dash="dot",
        line_color=COLORS["border_strong"],
    )
    fig = apply_standard_hover_layout(fig)
    fig.update_layout(
        margin=dict(l=48, r=16, t=45, b=35),
        height=360,
    )
    fig.update_xaxes(title_text="Distance (m)")
    fig.update_yaxes(title_text="Delta (s)")
    return fig
