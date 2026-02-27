import plotly.graph_objects as go
from fastf1.plotting import get_driver_style

from theme import COLORS

def adjust_color_brightness(hex_color, factor=0.8):
    hex_color = hex_color.lstrip("#")
    r, g, b = [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]

    r = int(max(0, min(255, r * factor)))
    g = int(max(0, min(255, g * factor)))
    b = int(max(0, min(255, b * factor)))

    return f"#{r:02x}{g:02x}{b:02x}"


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
        title="Track Layout",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, scaleanchor="x", scaleratio=1),
        margin=dict(l=10, r=10, t=40, b=10),
    )

    return fig


def build_binary_delta_track(delta_tel, driver1, driver2, faster_index, session):
    fig = go.Figure()

    driver1_abbr = session.get_driver(driver1)['Abbreviation']
    driver2_abbr = session.get_driver(driver2)['Abbreviation']

    color1 = get_driver_style(driver1_abbr, style=['color'], session=session)['color']
    color2 = get_driver_style(driver2_abbr, style=['color'], session=session)['color']

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

    # Binary colored segments
    for i in range(len(delta_tel) - 1):

        if delta_tel["Delta"].iloc[i] > 0:
            segment_color = slower_color
        else:
            segment_color = faster_color

        fig.add_trace(
            go.Scatter(
                x=[delta_tel["X"].iloc[i], delta_tel["X"].iloc[i+1]],
                y=[delta_tel["Y"].iloc[i], delta_tel["Y"].iloc[i+1]],
                mode="lines",
                line=dict(width=5, color=segment_color),
                showlegend=False,
                hoverinfo="skip"
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
            text=f"{faster_driver} vs {slower_driver}"
                 f"<br><sup>Colored by faster driver per segment</sup>",
            x=0.5
        ),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, scaleanchor="x", scaleratio=1),
        margin=dict(l=10, r=10, t=50, b=10),
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
