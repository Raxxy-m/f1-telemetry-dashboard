import plotly.graph_objects as go
from fastf1.plotting import get_compound_color

from theme import COLORS, apply_standard_hover_layout


def _format_lap_time(seconds_value):
    minutes = int(seconds_value // 60)
    seconds = seconds_value % 60
    return f"{minutes}:{seconds:06.3f}"


def create_lap_time_evolution_figure(df, fastest_idx, driver, session):
    fig = go.Figure()

    if df.empty:
        fig.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False))
        return fig

    plot_df = df.sort_values("LapNumber").copy()
    valid_df = plot_df[plot_df["IsValid"]].copy()
    invalid_df = plot_df[~plot_df["IsValid"]].copy()

    for compound in valid_df["Compound"].dropna().unique():
        compound_df = valid_df[valid_df["Compound"] == compound]
        color = get_compound_color(compound, session)

        fig.add_trace(
            go.Scatter(
                x=compound_df["LapNumber"],
                y=compound_df["LapTimeSeconds"],
                mode="markers+lines",
                name=str(compound),
                marker=dict(color=color, size=7),
                line=dict(color=color, width=1.8),
                hovertemplate=(
                    "Lap %{x}<br>"
                    "Lap Time: %{text}<br>"
                    f"Compound: {compound}<extra></extra>"
                ),
                text=compound_df["LapTimeFormatted"],
            )
        )

    if not invalid_df.empty:
        fig.add_trace(
            go.Scatter(
                x=invalid_df["LapNumber"],
                y=invalid_df["LapTimeSeconds"],
                mode="markers",
                marker=dict(
                    symbol="x",
                    color=COLORS["text_muted"],
                    size=8,
                    line=dict(width=1.2, color=COLORS["text_secondary"]),
                ),
                name="Invalid/Out lap",
                hovertemplate=(
                    "Lap %{x}<br>"
                    "Lap Time: %{y:.3f}s<br>"
                    "Marked invalid<extra></extra>"
                ),
            )
        )

    rolling = valid_df[["LapNumber", "LapTimeSeconds"]].copy()
    rolling["Rolling3"] = rolling["LapTimeSeconds"].rolling(3, min_periods=1).mean()
    fig.add_trace(
        go.Scatter(
            x=rolling["LapNumber"],
            y=rolling["Rolling3"],
            mode="lines",
            line=dict(color=COLORS["text_secondary"], width=1.9, dash="dot"),
            name="3-lap rolling avg",
            hovertemplate="Lap %{x}<br>Rolling Avg: %{y:.3f}s<extra></extra>",
        )
    )

    fastest_lap = plot_df.loc[fastest_idx]
    fastest_seconds = float(fastest_lap["LapTimeSeconds"])
    fastest_label = _format_lap_time(fastest_seconds)

    fig.add_trace(
        go.Scatter(
            x=[fastest_lap["LapNumber"]],
            y=[fastest_seconds],
            mode="markers+text",
            marker=dict(
                color=COLORS["fl_marker"],
                size=11,
                symbol="circle-dot",
                line=dict(width=1.2, color=COLORS["surface_1"]),
            ),
            text=["FL"],
            textposition="top center",
            showlegend=False,
            hovertemplate=(
                f"Fastest Lap {int(fastest_lap['LapNumber'])}<br>"
                f"Lap Time: {fastest_label}<extra></extra>"
            ),
        )
    )

    fig = apply_standard_hover_layout(fig)
    fig.update_layout(
        title=dict(
            text=f"{driver} Lap Time Evolution | Fastest: {fastest_label}",
            x=0.01,
        ),
        xaxis_title="Lap Number",
        yaxis_title="Lap Time (s)",
        margin=dict(l=48, r=16, t=52, b=38),
        height=430,
    )
    fig.update_yaxes(showgrid=False)
    fig.update_xaxes(showgrid=False)
    return fig
