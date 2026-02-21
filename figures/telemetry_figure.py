from plotly.subplots import make_subplots
import plotly.graph_objects as go

from theme import GRAPH_LAYOUT, Theme

from fastf1.plotting import get_driver_style

def build_telemetry_figure(driver_tel_dict, session):
    """
    Builds the grpahs for telemetry analysis
    
    :param driver_tel_dict: Drivers' Telemetery Information Dictionary
    """
    fig = make_subplots(
        rows=5,
        cols=1,
        shared_xaxes=True,
        # vertical_spacing=0.033,
        row_heights=[0.4, 0.18, 0.14, 0.16, 0.12],
        # subplot_titles=("Speed", "Throttle", "RPM", "Brake", "Gear")
    )

    # line styles

    for drv, tel in driver_tel_dict.items():

        driver_info = session.get_driver(drv)
        name_abbr = driver_info['Abbreviation']

        style = get_driver_style(name_abbr, style=['color', 'linestyle'], session=session)

        color = style['color']
        dash = "5px, 2px" if style['linestyle'] == 'dashed' else style['linestyle']
        
        #speed
        fig.add_trace(
            go.Scatter(
                x=tel["Distance"],
                y=tel["Speed"],
                mode="lines",
                name=name_abbr,
                line=dict(color=color, dash=dash, width=2),
                hovertemplate=f"{drv} Speed: %{{y:.1f}} km/h<extra></extra>"
            ),
            row=1, col=1
        )

        # Throttle
        fig.add_trace(
            go.Scatter(
                x=tel["Distance"],
                y=tel["Throttle"],
                mode="lines",
                line=dict(color=color, dash=dash),
                showlegend=False,
                hovertemplate=f"{drv} Throttle: %{{y:.0f}}% <extra></extra>"
            ),
            row=2, col=1
        )

        # RPM
        fig.add_trace(
            go.Scatter(
                x=tel["Distance"],
                y=tel["RPM"],
                mode="lines",
                line=dict(color=color, dash=dash),
                showlegend=False,
                hovertemplate=f"{drv} RPM: %{{y:.0f}}<extra></extra>"
            ),
            row=3, col=1
        )

        # Brake
        fig.add_trace(
            go.Scatter(
                x=tel["Distance"],
                y=tel["Brake"],
                mode="lines",
                fill="tozeroy",
                line=dict(color=color, dash=dash, shape='hv', width=0),
                opacity=0.4,
                showlegend=False,
                hovertemplate=f"{drv} Brake: %{{y:.0f}} <extra></extra>"
            ),
            row=4, col=1
        )

        # Gear
        fig.add_trace(
            go.Scatter(
                x=tel["Distance"],
                y=tel["nGear"],
                mode="lines",
                line=dict(color=color, dash=dash, shape='hv'),
                showlegend=False,
                hovertemplate=f"{drv} Gear: %{{y}} <extra></extra>"
            ),
            row=5, col=1
        )

    fig.update_layout(
        height=850,
        hovermode="x unified",
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            orientation="h",
            y=1.02
        )
    )

    fig.update_layout(**GRAPH_LAYOUT)

    fig.update_yaxes(title_text="Speed",range=[0, None], row=1, col=1)
    fig.update_yaxes(title_text="Throttle",range=[0, 100], row=2, col=1)
    fig.update_yaxes(title_text="RPM",range=[0, None], row=3, col=1)
    fig.update_yaxes(title_text="Brake",range=[0, 100], row=4, col=1)
    fig.update_yaxes(title_text="Gear",dtick=1, row=5, col=1)

    fig.update_yaxes(gridcolor=Theme.GRID_COLOR)
    fig.update_xaxes(gridcolor=Theme.GRID_COLOR)

    fig.update_yaxes(showgrid=False, row=2, col=1)
    fig.update_yaxes(showgrid=False, row=3, col=1)
    fig.update_yaxes(showgrid=False, row=4, col=1)
    fig.update_yaxes(showgrid=False, row=5, col=1)

    return fig