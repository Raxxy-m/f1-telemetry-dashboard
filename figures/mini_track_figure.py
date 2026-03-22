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
            name="Track",
            hoverinfo="skip",
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
                hoverinfo="skip",
            )
        )
    
    x_min = float(tel["X"].min())
    x_max = float(tel["X"].max())
    y_min = float(tel["Y"].min())
    y_max = float(tel["Y"].max())

    span_x = max(x_max - x_min, 1.0)
    span_y = max(y_max - y_min, 1.0)
    base_span = max(span_x, span_y)
    pad = base_span * 0.08
    half = (base_span / 2.0) + pad
    cx = (x_min + x_max) / 2.0
    cy = (y_min + y_max) / 2.0

    fig = apply_standard_hover_layout(fig)

    fig.update_layout(
        title={
            "text": "Track Position",
            "x": 0.5,
            "xanchor": "center",
            "y": 0.97,
        },
        hovermode=False,
        showlegend=False,
        margin=dict(l=8, r=8, t=38, b=8),
        xaxis=dict(
            visible=False,
            range=[cx - half, cx + half],
            fixedrange=True,
        ),
        yaxis=dict(
            visible=False,
            range=[cy - half, cy + half],
            scaleanchor="x",
            scaleratio=1,
            gridcolor=COLORS["grid"],
            fixedrange=True,
        ),
    )

    return fig
