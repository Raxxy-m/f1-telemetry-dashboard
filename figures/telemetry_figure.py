from plotly.subplots import make_subplots
import plotly.graph_objects as go
from fastf1.plotting import get_driver_style

from theme import COLORS, apply_standard_hover_layout


def _driver_style(session, driver):
    info = session.get_driver(driver)
    abbr = info["Abbreviation"]
    style = get_driver_style(abbr, style=["color", "linestyle"], session=session)
    dash = "dash" if style.get("linestyle") == "dashed" else "solid"
    return abbr, style["color"], dash


def build_telemetry_figure(driver_tel_dict, session):
    fig = make_subplots(
        rows=5,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.015,
        row_heights=[0.37, 0.18, 0.17, 0.16, 0.12],
    )

    for driver, tel in driver_tel_dict.items():
        abbr, color, dash = _driver_style(session, driver)
        label = f"{abbr} ({driver})"

        fig.add_trace(
            go.Scatter(
                x=tel["Distance"],
                y=tel["Speed"],
                mode="lines",
                name=label,
                line=dict(color=color, dash=dash, width=2.6),
                hovertemplate=(
                    f"{label}<br>"
                    "Distance: %{x:.0f} m<br>"
                    "Speed: %{y:.1f} km/h<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=tel["Distance"],
                y=tel["Throttle"],
                mode="lines",
                line=dict(color=color, dash=dash, width=1.9),
                showlegend=False,
                hovertemplate=(
                    f"{label}<br>"
                    "Distance: %{x:.0f} m<br>"
                    "Throttle: %{y:.0f}%<extra></extra>"
                ),
            ),
            row=2,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=tel["Distance"],
                y=tel["RPM"],
                mode="lines",
                line=dict(color=color, dash=dash, width=1.8),
                showlegend=False,
                hovertemplate=(
                    f"{label}<br>"
                    "Distance: %{x:.0f} m<br>"
                    "RPM: %{y:.0f}<extra></extra>"
                ),
            ),
            row=3,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=tel["Distance"],
                y=tel["Brake"],
                mode="lines",
                fill="tozeroy",
                line=dict(color=color, dash=dash, shape="hv", width=1.2),
                opacity=0.35,
                showlegend=False,
                hovertemplate=(
                    f"{label}<br>"
                    "Distance: %{x:.0f} m<br>"
                    "Brake: %{y:.0f}%<extra></extra>"
                ),
            ),
            row=4,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=tel["Distance"],
                y=tel["nGear"],
                mode="lines",
                line=dict(color=color, dash=dash, shape="hv", width=1.7),
                showlegend=False,
                hovertemplate=(
                    f"{label}<br>"
                    "Distance: %{x:.0f} m<br>"
                    "Gear: %{y}<extra></extra>"
                ),
            ),
            row=5,
            col=1,
        )

    fig = apply_standard_hover_layout(fig)
    fig.update_layout(
        height=910,
        margin=dict(l=52, r=16, t=36, b=34),
        legend=dict(
            bgcolor="rgba(17, 23, 34, 0.45)",
            orientation="h",
            y=0.995,
            x=0,
            yanchor="top",
            xanchor="left",
        ),
    )

    fig.update_yaxes(title_text="Speed (km/h)", rangemode="tozero", row=1, col=1)
    fig.update_yaxes(title_text="Throttle (%)", range=[0, 100], row=2, col=1)
    fig.update_yaxes(title_text="RPM", rangemode="tozero", row=3, col=1)
    fig.update_yaxes(title_text="Brake (%)", range=[0, 100], row=4, col=1)
    fig.update_yaxes(title_text="Gear", dtick=1, row=5, col=1)
    fig.update_xaxes(title_text="Distance (m)", row=5, col=1)

    fig.update_yaxes(gridcolor=COLORS["grid"])
    fig.update_xaxes(gridcolor=COLORS["grid"])
    fig.update_yaxes(showgrid=False, row=2, col=1)
    fig.update_yaxes(showgrid=False, row=3, col=1)
    fig.update_yaxes(showgrid=False, row=4, col=1)
    fig.update_yaxes(showgrid=False, row=5, col=1)

    return fig
