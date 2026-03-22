import plotly.graph_objects as go
from fastf1.plotting import get_driver_style
import numpy as np

from theme import COLORS, apply_standard_hover_layout


def _format_lap_time(seconds_value):
    minutes = int(seconds_value // 60)
    seconds = seconds_value % 60
    return f"{minutes}:{seconds:06.3f}"


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
        height=420,
    )
    return fig


def create_lap_time_evolution_figure(driver_payloads, session):
    if not driver_payloads:
        return _message_figure("No lap data available for the selected driver(s).")

    if len(driver_payloads) > 2:
        return _message_figure("Select up to 2 drivers for lap-time evolution comparison.")

    fig = go.Figure()
    all_valid_times = []

    for idx, payload in enumerate(driver_payloads):
        driver = payload["driver"]
        df = payload["df"]
        fastest_idx = payload["fastest_idx"]

        if df.empty:
            continue

        info = session.get_driver(driver)
        abbr = info["Abbreviation"]
        color = get_driver_style(abbr, style=["color"], session=session)["color"]

        plot_df = df.sort_values("LapNumber").copy()
        valid_df = plot_df[plot_df["IsValid"]].copy()
        invalid_df = plot_df[~plot_df["IsValid"]].copy()

        if valid_df.empty:
            continue
        all_valid_times.extend(valid_df["LapTimeSeconds"].tolist())

        fig.add_trace(
            go.Scatter(
                x=valid_df["LapNumber"],
                y=valid_df["LapTimeSeconds"],
                mode="markers+lines",
                name=f"{abbr} ({driver})",
                marker=dict(color=color, size=6),
                line=dict(color=color, width=2.0),
                hovertemplate=(
                    f"{abbr} ({driver})<br>"
                    "Lap %{x}<br>"
                    "Lap Time: %{text}<br>"
                    "Compound: %{customdata}<extra></extra>"
                ),
                text=valid_df["LapTimeFormatted"],
                customdata=valid_df["Compound"].fillna("-"),
            )
        )

        rolling = valid_df[["LapNumber", "LapTimeSeconds"]].copy()
        rolling["Rolling3"] = rolling["LapTimeSeconds"].rolling(3, min_periods=1).mean()
        fig.add_trace(
            go.Scatter(
                x=rolling["LapNumber"],
                y=rolling["Rolling3"],
                mode="lines",
                line=dict(color=color, width=1.4, dash="dot"),
                name=f"{abbr} rolling avg",
                opacity=0.75,
                hovertemplate=f"{abbr}<br>Lap %{{x}}<br>Rolling Avg: %{{y:.3f}}s<extra></extra>",
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
                        color=color,
                        size=7,
                        line=dict(width=1.0, color=COLORS["surface_1"]),
                    ),
                    name=f"{abbr} invalid lap",
                    showlegend=idx == 0,
                    hovertemplate=(
                        f"{abbr}<br>"
                        "Lap %{x}<br>"
                        "Lap Time: %{y:.3f}s<br>"
                        "Marked invalid<extra></extra>"
                    ),
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
                    color=color,
                    size=10,
                    symbol="diamond",
                    line=dict(width=1.0, color=COLORS["surface_1"]),
                ),
                text=["FL"],
                textposition="top center",
                name=f"{abbr} fastest",
                showlegend=False,
                hovertemplate=(
                    f"{abbr} Fastest Lap {int(fastest_lap['LapNumber'])}<br>"
                    f"Lap Time: {fastest_label}<extra></extra>"
                ),
            )
        )

    fig = apply_standard_hover_layout(fig)
    title = "Lap Time Trend Comparison" if len(driver_payloads) == 2 else "Lap Time Trend"
    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center"),
        xaxis_title="Lap Number",
        yaxis_title="Lap Time (s)",
        margin=dict(l=56, r=18, t=74, b=56),
        height=420,
        legend=dict(orientation="h", y=1.02, x=0),
    )

    if all_valid_times:
        values = np.array(all_valid_times, dtype=float)
        values = values[np.isfinite(values)]
        if values.size > 0:
            q1, q3 = np.percentile(values, [25, 75])
            iqr = max(q3 - q1, 0.22)
            robust_low = max(0.0, q1 - 1.4 * iqr)
            robust_high = q3 + 2.2 * iqr

            inlier_values = values[(values >= robust_low) & (values <= robust_high)]
            if inlier_values.size == 0:
                inlier_values = values

            y_min = float(np.min(inlier_values))
            y_max = float(np.max(inlier_values))
            spread = max(y_max - y_min, 0.2)
            pad = max(0.24, spread * 0.16)
            fig.update_yaxes(range=[y_min - pad, y_max + pad])

            outlier_count = int(np.sum((values < robust_low) | (values > robust_high)))
            if outlier_count > 0:
                fig.add_annotation(
                    x=0.99,
                    y=1.03,
                    xref="paper",
                    yref="paper",
                    xanchor="right",
                    yanchor="bottom",
                    showarrow=False,
                    text=f"{outlier_count} outlier lap(s) clipped by y-scale",
                    font=dict(size=10, color=COLORS["text_tertiary"]),
                )

    fig.update_yaxes(showgrid=False, automargin=True)
    fig.update_xaxes(showgrid=False, automargin=True)
    return fig
