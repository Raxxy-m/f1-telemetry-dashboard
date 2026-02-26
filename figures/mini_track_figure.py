import plotly.graph_objects as go
from theme import GRAPH_LAYOUT, Theme, apply_standard_hover_layout

def build_mini_track(driver_tel, driver_styles, reference_distance):
    """
    TODO: Add comments
    """

    fig = go.Figure()

    # Plot track using first driver as reference
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

    if reference_distance is not None:

        # Find nearest telemetry row
        idx = (tel["Distance"] - reference_distance).abs().idxmin()

        fig.add_trace(
            go.Scatter(
                x=[tel.loc[idx, "X"]],
                y=[tel.loc[idx, "Y"]],
                mode="markers",
                marker=dict(
                    size=10,
                    color=driver_styles[first_driver]["color"]
                ),
                name=driver_styles[first_driver]["label"]
            )
        )
    
    fig = apply_standard_hover_layout(fig)

    fig.update_layout(
        title={
            "text": "Track Position",
            "x": 0.5,
            "xanchor": "center"
        },
        showlegend=False,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, scaleanchor="x", scaleratio=1, gridcolor=Theme.GRID_COLOR),
    )
    
    fig.update_layout(**GRAPH_LAYOUT)

    return fig
