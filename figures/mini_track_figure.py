import plotly.graph_objects as go
from theme import COLORS, apply_standard_hover_layout


def build_mini_track(driver_tel, driver_styles, reference_distance):
    fig = go.Figure()

    if not driver_tel:
        fig.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False))
        return fig

    first_driver = list(driver_tel.keys())[0]
    tel = driver_tel[first_driver]

    fig.add_trace(
        go.Scatter(
            x=tel["X"],
            y=tel["Y"],
            mode="lines",
            line=dict(color="#888", width=2),
            name="Track"
        )
    )

    for drv, drv_tel in driver_tel.items():
        style = driver_styles.get(drv, {})
        marker_color = style.get("color", COLORS["telemetry_2"])
        marker_name = style.get("label", str(drv))

        if reference_distance is not None:
            idx = (drv_tel["Distance"] - reference_distance).abs().idxmin()
        else:
            idx = drv_tel["Distance"].idxmin()

        fig.add_trace(
            go.Scatter(
                x=[drv_tel.loc[idx, "X"]],
                y=[drv_tel.loc[idx, "Y"]],
                mode="markers",
                marker=dict(
                    size=10,
                    color=marker_color,
                    line=dict(width=1.5, color=COLORS["surface_2"]),
                ),
                name=marker_name,
                hovertemplate=(
                    f"{marker_name}<br>"
                    "X: %{x:.0f}<br>"
                    "Y: %{y:.0f}<extra></extra>"
                ),
            )
        )
    
    fig = apply_standard_hover_layout(fig)

    fig.update_layout(
        title={
            "text": "Track Position",
            "x": 0.5,
            "xanchor": "center",
            "y": 0.98,
        },
        showlegend=len(driver_tel) > 1,
        legend=dict(
            orientation="h",
            y=-0.08,
            x=0.5,
            xanchor="center",
            yanchor="top",
        ),
        margin=dict(l=10, r=10, t=54, b=36),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, scaleanchor="x", scaleratio=1, gridcolor=COLORS['grid']),
    )

    return fig
