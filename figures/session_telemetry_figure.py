import plotly.graph_objects as go
from theme import COLORS, apply_standard_hover_layout

def create_full_session_speed_figure(telemetry, driver, lap_number):
    """
    TODO: Add comments
    """
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=telemetry["Distance"],
            y=telemetry["Speed"],
            mode="lines",
            name=f"Lap {lap_number}",
            line=dict(width=2),
        )
    )

    fig.update_layout(
        title=dict(
            text=f"{driver} – Lap {lap_number} Speed Trace",
            x=0.5
        ),
        xaxis_title="Distance (m)",
        yaxis_title="Speed (km/h)",
        margin=dict(l=40, r=40, t=60, b=40),
    )

    # fig.update_yaxes(gridcolor=Theme.GRID_COLOR)
    fig = apply_standard_hover_layout(fig)
    fig.update_xaxes(gridcolor=COLORS['grid'])
    fig.update_yaxes(showgrid=False)

    return fig
