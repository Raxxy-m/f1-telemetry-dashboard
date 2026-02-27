import plotly.graph_objects as go
from fastf1.plotting import get_compound_color

from theme import COLORS, apply_standard_hover_layout

def create_lap_time_evolution_figure(df, fastest_idx, driver, session):
    """
    TODO: Add comments
    """

    fig = go.Figure()
    compounds = df['Compound'].dropna().unique()

    for compound in compounds:
        compound_df = df[df['Compound'] == compound]

        color = get_compound_color(compound, session)

        # Valid laps
        valid_df = compound_df[compound_df["IsValid"]]

        fig.add_trace(
            go.Scatter(
                x=valid_df["LapNumber"],
                y=valid_df["LapTimeSeconds"],
                mode="markers+lines",
                name=f"{compound}",
                marker=dict(color=color, size=8),
                line=dict(color=color),
                hovertemplate=(
                    "Lap %{x}<br>"
                    "Lap Time %{text}<br>"
                    f"Compound: {compound}<br>"
                    "<extra></extra>"
                ),
                text=valid_df["LapTimeFormatted"]
            )
        )


        # Fastest Lap Marker
        fastest_lap = df.loc[fastest_idx]

        fig.add_trace(
            go.Scatter(
                x=[fastest_lap["LapNumber"]],
                y=[fastest_lap["LapTimeSeconds"]],
                mode="markers+text",
                marker=dict(
                    color=COLORS['fl_marker'],
                    size=12,
                    symbol="circle-dot"
                ),
                text=["(FL)"],
                textposition="top center",
                showlegend=False
            )
        )
        fig = apply_standard_hover_layout(fig)

        fig.update_layout(
            title=dict(
                text=f"{driver} – Lap Time Evolution",
                x=0.5
            ),
            xaxis_title="Lap Number",
            yaxis_title="Lap Time",
            margin=dict(l=40, r=40, t=60, b=40),
        )

        # Format y-axis as mm:ss.SSS
        fig.update_yaxes(
            tickformat="%M:%S.%L"
        )
        fig.update_yaxes(showgrid=False)
        fig.update_xaxes(showgrid=False)

    return fig
