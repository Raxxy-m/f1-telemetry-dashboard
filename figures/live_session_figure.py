from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

DASH_SEQUENCE = ("solid", "dash", "dot", "dashdot", "longdash", "longdashdot")


def _message_figure(message: str, height: int = 430) -> go.Figure:
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
                font=dict(size=14, color="#93a1b5"),
            )
        ],
        margin=dict(l=16, r=16, t=40, b=16),
        height=height,
    )
    return fig


def _line_color(group: pd.DataFrame, default: str = "#4da3ff") -> str:
    if "team_color" not in group.columns:
        return default
    valid = group["team_color"].dropna()
    if valid.empty:
        return default
    return str(valid.iloc[0])


def _format_lap_time(seconds: Any) -> str:
    if seconds is None:
        return "-"
    try:
        value = float(seconds)
    except (TypeError, ValueError):
        return "-"
    minutes = int(value // 60)
    rem = value - (minutes * 60)
    return f"{minutes:02d}.{rem:06.3f}"


def _legend_style(show_legend: bool) -> dict[str, Any]:
    return {
        "showlegend": show_legend,
        "legend": dict(
            orientation="h",
            yanchor="bottom",
            y=1.06,
            xanchor="left",
            x=0,
            font=dict(size=11),
            bgcolor="rgba(0,0,0,0)",
        ),
    }


def _lap_axis(title: str = "Lap Number") -> dict[str, Any]:
    return {
        "title_text": title,
        "tickmode": "linear",
        "dtick": 1,
        "tickformat": ".0f",
        "automargin": True,
    }


def _lap_time_axis(values: Any, title: str = "Lap Time (mm.ss.SSS)") -> dict[str, Any]:
    series = pd.Series(values).dropna()
    if series.empty:
        return {"title_text": title, "automargin": True}

    series = series.astype(float)
    min_v = float(series.min())
    max_v = float(series.max())

    if abs(max_v - min_v) < 1e-9:
        tick_vals = [min_v]
    else:
        steps = 6
        step = (max_v - min_v) / float(steps - 1)
        tick_vals = [min_v + (idx * step) for idx in range(steps)]

    return {
        "title_text": title,
        "tickmode": "array",
        "tickvals": tick_vals,
        "ticktext": [_format_lap_time(v) for v in tick_vals],
        "automargin": True,
    }


def _driver_dash_map(df: pd.DataFrame) -> dict[str, str]:
    if df.empty or "driver_label" not in df.columns:
        return {}

    driver_labels = df["driver_label"].dropna().astype(str)
    if driver_labels.empty:
        return {}

    if "team_name" in df.columns:
        team_key = df["team_name"].fillna("").astype(str)
    elif "team_color" in df.columns:
        team_key = df["team_color"].fillna("").astype(str)
    else:
        return {label: "solid" for label in sorted(driver_labels.unique())}

    style_df = pd.DataFrame(
        {
            "driver_label": driver_labels,
            "_team_key": team_key,
        }
    ).drop_duplicates(subset=["driver_label"])

    dash_map: dict[str, str] = {}
    for _, group in style_df.groupby("_team_key", sort=True):
        labels = sorted(group["driver_label"].astype(str).tolist())
        if len(labels) == 1:
            dash_map[labels[0]] = "solid"
            continue
        for idx, label in enumerate(labels):
            dash_map[label] = DASH_SEQUENCE[idx % len(DASH_SEQUENCE)]

    for label in sorted(driver_labels.unique()):
        dash_map.setdefault(label, "solid")
    return dash_map


def _add_safety_lap_overlays(
    fig: go.Figure,
    safety_laps: list[int],
    row: int | None = None,
    col: int | None = None,
) -> None:
    overlay_kwargs: dict[str, int] = {}
    if row is not None:
        overlay_kwargs["row"] = row
    if col is not None:
        overlay_kwargs["col"] = col

    for lap in sorted(set(int(l) for l in safety_laps if l is not None)):
        fig.add_vrect(
            x0=lap - 0.5,
            x1=lap + 0.5,
            fillcolor="rgba(255,176,32,0.14)",
            line_width=0,
            layer="below",
            **overlay_kwargs,
        )


def _session_profile(session_category: str, is_sprint_session: bool = False) -> dict[str, Any]:
    if session_category == "race":
        pace_subtitle = (
            "Sprint-adaptive smoothing: 2-lap early, then 3-lap once enough clean laps exist."
            if is_sprint_session
            else "Clean laps only (pit laps excluded) with fastest clean lap highlighted."
        )
        return {
            "profile_note": "Race session detected: focus is positions, race gaps and sustainable race pace.",
            "cards": [
                {
                    "kicker": "Raceboard",
                    "title": "Position vs Lap",
                    "subtitle": "Includes pit-lap markers and safety-car lap shading when available.",
                },
                {
                    "kicker": "Gaps",
                    "title": "Gap To Leader / Car Ahead",
                    "subtitle": "Race control view for pace compression and overtake pressure.",
                },
                {
                    "kicker": "Pace",
                    "title": "Rolling 3-Lap Evolution",
                    "subtitle": pace_subtitle,
                },
            ],
        }
    if session_category == "qualifying":
        return {
            "profile_note": "Qualifying session detected: focus is peak pace, provisional pole trend, and speed extraction.",
            "cards": [
                {
                    "kicker": "Qualifying",
                    "title": "Best Lap Progression",
                    "subtitle": "Tracks when each driver improves their best lap through the session.",
                },
                {
                    "kicker": "Qualifying",
                    "title": "Gap To Provisional Pole",
                    "subtitle": "Delta between each driver best lap and the live provisional pole benchmark.",
                },
                {
                    "kicker": "Qualifying",
                    "title": "Best Lap vs Top Speed",
                    "subtitle": "Trade-off view between pure lap time and straight-line speed.",
                },
            ],
        }
    return {
        "profile_note": "Practice/Test session detected: focus is long-run behavior, pit-cycle pattern, and consistency.",
        "cards": [
            {
                "kicker": "Practice",
                "title": "Long-Run Pace Trend",
                "subtitle": "Rolling 5-lap average on clean laps to smooth fuel/traffic noise.",
            },
            {
                "kicker": "Practice",
                "title": "Run Volume & Pit Cycles",
                "subtitle": "Completed laps and pit-stop activity by driver.",
            },
            {
                "kicker": "Practice",
                "title": "Best Lap vs Consistency",
                "subtitle": "Compare peak lap pace against lap-time variability.",
            },
        ],
    }


def build_live_race_figures(
    position_df: pd.DataFrame,
    pit_lap_df: pd.DataFrame,
    safety_laps: list[int],
    gap_df: pd.DataFrame,
    pace_df: pd.DataFrame,
    fastest_lap_row: dict[str, Any] | None,
    is_sprint_session: bool = False,
) -> tuple[go.Figure, go.Figure, go.Figure]:
    fig1 = _build_race_position_figure(position_df, pit_lap_df, safety_laps)
    fig2 = _build_race_gap_figure(gap_df, safety_laps)
    fig3 = _build_race_pace_figure(pace_df, fastest_lap_row, safety_laps, is_sprint_session)
    return fig1, fig2, fig3


def _build_race_position_figure(
    position_df: pd.DataFrame,
    pit_lap_df: pd.DataFrame,
    safety_laps: list[int],
) -> go.Figure:
    if position_df.empty:
        return _message_figure("Waiting for position/lap packets from live feed.")

    driver_count = int(position_df["driver_label"].nunique())
    show_legend = driver_count <= 8
    dash_map = _driver_dash_map(position_df)

    fig = go.Figure()
    for driver_label, group in position_df.groupby("driver_label", sort=True):
        color = _line_color(group)
        sorted_group = group.sort_values("lap_number")
        fig.add_trace(
            go.Scatter(
                x=sorted_group["lap_number"],
                y=sorted_group["position"],
                mode="lines+markers",
                name=str(driver_label),
                line=dict(color=color, width=2.2, dash=dash_map.get(str(driver_label), "solid")),
                marker=dict(size=6, color=color),
                hovertemplate=(
                    "Driver: %{fullData.name}<br>"
                    "Lap: %{x}<br>"
                    "Position: %{y}<extra></extra>"
                ),
            )
        )

    if not pit_lap_df.empty:
        for _, row in pit_lap_df.iterrows():
            fig.add_trace(
                go.Scatter(
                    x=[row["lap_number"]],
                    y=[row["position"]],
                    mode="markers",
                    marker=dict(symbol="x", size=10, color=row.get("team_color") or "#f5f5f5"),
                    showlegend=False,
                    hovertemplate=(
                        f"Driver: {row['driver_label']}<br>"
                        "Lap: %{x}<br>"
                        "Position: %{y}<br>"
                        "Pit Lap<extra></extra>"
                    ),
                )
            )

    _add_safety_lap_overlays(fig, safety_laps)

    max_position = int(position_df["position"].max())
    fig.update_layout(
        hovermode="x unified",
        height=430,
        margin=dict(l=8, r=8, t=72, b=32),
        **_legend_style(show_legend),
    )
    fig.update_xaxes(**_lap_axis())
    fig.update_yaxes(
        title_text="Position (1 = Leader)",
        autorange="reversed",
        tickmode="linear",
        tick0=1,
        dtick=1,
        range=[max_position + 0.5, 0.5],
        automargin=True,
    )
    return fig


def _build_race_gap_figure(gap_df: pd.DataFrame, safety_laps: list[int]) -> go.Figure:
    if gap_df.empty:
        return _message_figure("Waiting for gap fields (TimeDiffToFastest/PositionAhead).")

    driver_count = int(gap_df["driver_label"].nunique())
    show_legend = driver_count <= 7
    dash_map = _driver_dash_map(gap_df)
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Gap To Leader (s)", "Gap To Car Ahead (s)"),
        horizontal_spacing=0.12,
    )

    for driver_label, group in gap_df.groupby("driver_label", sort=True):
        color = _line_color(group)
        sorted_group = group.sort_values("lap_number")

        leader_slice = sorted_group.dropna(subset=["gap_to_leader_s"])
        if not leader_slice.empty:
            fig.add_trace(
                go.Scatter(
                    x=leader_slice["lap_number"],
                    y=leader_slice["gap_to_leader_s"],
                    mode="lines+markers",
                    name=str(driver_label),
                    line=dict(color=color, width=2, dash=dash_map.get(str(driver_label), "solid")),
                    marker=dict(size=5),
                    legendgroup=str(driver_label),
                    showlegend=show_legend,
                ),
                row=1,
                col=1,
            )

        ahead_slice = sorted_group.dropna(subset=["gap_to_ahead_s"])
        if not ahead_slice.empty:
            fig.add_trace(
                go.Scatter(
                    x=ahead_slice["lap_number"],
                    y=ahead_slice["gap_to_ahead_s"],
                    mode="lines+markers",
                    name=str(driver_label),
                    line=dict(color=color, width=2, dash=dash_map.get(str(driver_label), "solid")),
                    marker=dict(size=5),
                    legendgroup=str(driver_label),
                    showlegend=False,
                ),
                row=1,
                col=2,
            )

    fig.update_layout(
        hovermode="x unified",
        height=430,
        margin=dict(l=8, r=8, t=72, b=32),
        **_legend_style(show_legend),
    )
    _add_safety_lap_overlays(fig, safety_laps, row=1, col=1)
    _add_safety_lap_overlays(fig, safety_laps, row=1, col=2)
    fig.update_xaxes(row=1, col=1, **_lap_axis())
    fig.update_xaxes(row=1, col=2, **_lap_axis())
    fig.update_yaxes(title_text="Seconds", row=1, col=1, automargin=True)
    fig.update_yaxes(title_text="Seconds", row=1, col=2, automargin=True)
    return fig


def _build_race_pace_figure(
    pace_df: pd.DataFrame,
    fastest_lap_row: dict[str, Any] | None,
    safety_laps: list[int],
    is_sprint_session: bool = False,
) -> go.Figure:
    if pace_df.empty:
        return _message_figure("Waiting for clean lap-time packets to build pace trend.")

    pace_column = "rolling_race_pace_s" if "rolling_race_pace_s" in pace_df.columns else "rolling_3lap_s"
    driver_count = int(pace_df["driver_label"].nunique())
    show_legend = driver_count <= 8
    dash_map = _driver_dash_map(pace_df)
    fig = go.Figure()
    for driver_label, group in pace_df.groupby("driver_label", sort=True):
        color = _line_color(group)
        sorted_group = group.sort_values("lap_number")
        hover_lap_times = sorted_group[pace_column].map(_format_lap_time)
        if "rolling_window" in sorted_group.columns:
            rolling_windows = sorted_group["rolling_window"].fillna(3).astype(int)
            custom_data = pd.DataFrame(
                {
                    "pace_label": hover_lap_times,
                    "window": rolling_windows,
                }
            )
            hover_template = (
                "Driver: %{fullData.name}<br>"
                "Lap: %{x}<br>"
                "Rolling Pace: %{customdata[0]}<br>"
                "Window: %{customdata[1]} lap(s)<extra></extra>"
            )
        else:
            custom_data = hover_lap_times
            hover_template = (
                "Driver: %{fullData.name}<br>"
                "Lap: %{x}<br>"
                "Rolling Pace: %{customdata}<extra></extra>"
            )
        fig.add_trace(
            go.Scatter(
                x=sorted_group["lap_number"],
                y=sorted_group[pace_column],
                customdata=custom_data,
                mode="lines+markers",
                name=str(driver_label),
                line=dict(color=color, width=2.2, dash=dash_map.get(str(driver_label), "solid")),
                marker=dict(size=6),
                hovertemplate=hover_template,
            )
        )

    if fastest_lap_row:
        fastest_time = _format_lap_time(fastest_lap_row.get("last_lap_time_s"))
        fig.add_trace(
            go.Scatter(
                x=[fastest_lap_row.get("lap_number")],
                y=[fastest_lap_row.get("last_lap_time_s")],
                customdata=[fastest_time],
                mode="markers",
                name="Fastest Clean Lap",
                marker=dict(symbol="star", size=14, color="#FF1801"),
                showlegend=show_legend,
                hovertemplate=(
                    "Marker: Fastest Clean Lap<br>"
                    "Lap: %{x}<br>"
                    "Lap Time: %{customdata}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        hovermode="x unified",
        height=430,
        margin=dict(l=8, r=8, t=72, b=32),
        **_legend_style(show_legend),
    )
    _add_safety_lap_overlays(fig, safety_laps)
    fig.update_xaxes(**_lap_axis())
    fig.update_yaxes(
        **_lap_time_axis(
            pace_df[pace_column],
            title=(
                "Rolling Pace (2->3 lap adaptive)"
                if is_sprint_session
                else "Rolling Pace (3-lap)"
            ),
        )
    )
    return fig


def build_live_qualifying_figures(
    bestlap_df: pd.DataFrame,
    bestlap_summary_df: pd.DataFrame,
) -> tuple[go.Figure, go.Figure, go.Figure]:
    return (
        _build_quali_best_progression(bestlap_df),
        _build_quali_gap_to_pole(bestlap_df),
        _build_quali_best_vs_speed(bestlap_summary_df),
    )


def _build_quali_best_progression(bestlap_df: pd.DataFrame) -> go.Figure:
    if bestlap_df.empty:
        return _message_figure("Waiting for qualifying best-lap updates.")

    driver_count = int(bestlap_df["driver_label"].nunique())
    show_legend = driver_count <= 10
    dash_map = _driver_dash_map(bestlap_df)

    fig = go.Figure()
    for driver_label, group in bestlap_df.groupby("driver_label", sort=True):
        color = _line_color(group)
        run = (
            group.sort_values("best_lap_lap")
            .drop_duplicates(subset=["best_lap_lap"], keep="last")
        )
        hover_lap_times = run["best_lap_time_s"].map(_format_lap_time)
        fig.add_trace(
            go.Scatter(
                x=run["best_lap_lap"],
                y=run["best_lap_time_s"],
                customdata=hover_lap_times,
                mode="lines+markers",
                name=str(driver_label),
                line=dict(color=color, width=2, dash=dash_map.get(str(driver_label), "solid")),
                marker=dict(size=6),
                hovertemplate=(
                    "Driver: %{fullData.name}<br>"
                    "Lap: %{x}<br>"
                    "Best Lap: %{customdata}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        hovermode="x unified",
        height=430,
        margin=dict(l=8, r=8, t=72, b=32),
        **_legend_style(show_legend),
    )
    fig.update_xaxes(**_lap_axis("Lap Number Where Best Was Set"))
    fig.update_yaxes(**_lap_time_axis(bestlap_df["best_lap_time_s"]))
    return fig


def _build_quali_gap_to_pole(bestlap_df: pd.DataFrame) -> go.Figure:
    if bestlap_df.empty:
        return _message_figure("Waiting for best-lap updates to compute provisional pole gap.")

    df = bestlap_df.sort_values("seq").copy()
    df["provisional_pole_s"] = df["best_lap_time_s"].cummin()
    df["gap_to_pole_s"] = df["best_lap_time_s"] - df["provisional_pole_s"]
    driver_count = int(df["driver_label"].nunique())
    show_legend = driver_count <= 10
    dash_map = _driver_dash_map(df)

    fig = go.Figure()
    for driver_label, group in df.groupby("driver_label", sort=True):
        color = _line_color(group)
        run = group.sort_values("best_lap_lap")
        fig.add_trace(
            go.Scatter(
                x=run["best_lap_lap"],
                y=run["gap_to_pole_s"],
                mode="lines+markers",
                name=str(driver_label),
                line=dict(color=color, width=2, dash=dash_map.get(str(driver_label), "solid")),
                marker=dict(size=6),
            )
        )

    fig.update_layout(
        hovermode="x unified",
        height=430,
        margin=dict(l=8, r=8, t=72, b=32),
        **_legend_style(show_legend),
    )
    fig.update_xaxes(**_lap_axis())
    fig.update_yaxes(title_text="Gap (s)", automargin=True)
    return fig


def _build_quali_best_vs_speed(bestlap_summary_df: pd.DataFrame) -> go.Figure:
    if bestlap_summary_df.empty:
        return _message_figure("Waiting for enough data to compare best lap and top speed.")

    df = bestlap_summary_df.dropna(subset=["best_lap_s", "max_speed_trap_kph"])
    if df.empty:
        return _message_figure("Waiting for best-lap and speed-trap pairs.")

    fig = go.Figure()
    for _, row in df.iterrows():
        lap_time_label = _format_lap_time(row["best_lap_s"])
        fig.add_trace(
            go.Scatter(
                x=[row["best_lap_s"]],
                y=[row["max_speed_trap_kph"]],
                customdata=[lap_time_label],
                mode="markers+text",
                text=[row["driver_label"]],
                textposition="top center",
                marker=dict(
                    size=11,
                    color=row.get("team_color") or "#4da3ff",
                    line=dict(width=1, color="rgba(0,0,0,0.35)"),
                ),
                showlegend=False,
                hovertemplate=(
                    f"Driver: {row['driver_label']}<br>"
                    "Best Lap: %{customdata}<br>"
                    f"Top Speed: {row['max_speed_trap_kph']:.1f} km/h<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        height=430,
        margin=dict(l=8, r=8, t=56, b=30),
        showlegend=False,
    )
    fig.update_xaxes(**_lap_time_axis(df["best_lap_s"], title="Best Lap (mm.ss.SSS)"))
    fig.update_yaxes(title_text="Top Speed Trap (km/h)", automargin=True)
    return fig


def build_live_practice_figures(
    pace_df: pd.DataFrame,
    stint_summary_df: pd.DataFrame,
    bestlap_summary_df: pd.DataFrame,
) -> tuple[go.Figure, go.Figure, go.Figure]:
    return (
        _build_practice_long_run(pace_df),
        _build_practice_stint_summary(stint_summary_df),
        _build_practice_best_vs_consistency(pace_df, bestlap_summary_df),
    )


def _build_practice_long_run(pace_df: pd.DataFrame) -> go.Figure:
    if pace_df.empty:
        return _message_figure("Waiting for clean laps to build long-run pace trend.")

    df = pace_df.copy()
    df["rolling_5lap_s"] = (
        df.groupby("driver_no")["last_lap_time_s"]
        .transform(lambda s: s.rolling(window=5, min_periods=2).mean())
    )
    df = df.dropna(subset=["rolling_5lap_s"])
    if df.empty:
        return _message_figure("Need at least 2 clean laps per driver for rolling pace.")

    driver_count = int(df["driver_label"].nunique())
    show_legend = driver_count <= 10
    dash_map = _driver_dash_map(df)
    fig = go.Figure()
    for driver_label, group in df.groupby("driver_label", sort=True):
        color = _line_color(group)
        run = group.sort_values("lap_number")
        hover_lap_times = run["rolling_5lap_s"].map(_format_lap_time)
        fig.add_trace(
            go.Scatter(
                x=run["lap_number"],
                y=run["rolling_5lap_s"],
                customdata=hover_lap_times,
                mode="lines+markers",
                name=str(driver_label),
                line=dict(color=color, width=2.1, dash=dash_map.get(str(driver_label), "solid")),
                marker=dict(size=5),
                hovertemplate=(
                    "Driver: %{fullData.name}<br>"
                    "Lap: %{x}<br>"
                    "Rolling Pace: %{customdata}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        hovermode="x unified",
        height=430,
        margin=dict(l=8, r=8, t=72, b=32),
        **_legend_style(show_legend),
    )
    fig.update_xaxes(**_lap_axis())
    fig.update_yaxes(**_lap_time_axis(df["rolling_5lap_s"]))
    return fig


def _build_practice_stint_summary(stint_summary_df: pd.DataFrame) -> go.Figure:
    if stint_summary_df.empty:
        return _message_figure("Waiting for completed-lap and pit-stop counters.")

    df = stint_summary_df.sort_values("completed_laps", ascending=False)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=df["driver_label"],
            y=df["completed_laps"],
            name="Completed Laps",
            marker=dict(
                color=[color if color else "#FF4D5A" for color in df["team_color"]],
                line=dict(width=1, color="rgba(0,0,0,0.2)"),
            ),
            opacity=0.9,
            text=df["completed_laps"],
            textposition="outside",
            cliponaxis=False,
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=df["driver_label"],
            y=df["pit_stops"],
            mode="lines+markers",
            name="Pit Stops",
            marker=dict(size=8, color="#FFB020"),
            line=dict(width=2, color="#FFB020"),
        ),
        secondary_y=True,
    )
    fig.update_layout(
        height=430,
        margin=dict(l=8, r=8, t=72, b=30),
        **_legend_style(True),
    )
    fig.update_xaxes(title_text="Driver", automargin=True)
    fig.update_yaxes(title_text="Completed Laps", secondary_y=False)
    fig.update_yaxes(title_text="Pit Stops", secondary_y=True)
    return fig


def _build_practice_best_vs_consistency(
    pace_df: pd.DataFrame,
    bestlap_summary_df: pd.DataFrame,
) -> go.Figure:
    if pace_df.empty or bestlap_summary_df.empty:
        return _message_figure("Waiting for lap-time distribution to compute consistency.")

    variability = (
        pace_df.groupby("driver_no", as_index=False)["last_lap_time_s"]
        .std()
        .rename(columns={"last_lap_time_s": "lap_time_std_s"})
    )
    df = bestlap_summary_df.merge(variability, on="driver_no", how="left")
    df = df.dropna(subset=["best_clean_lap_s", "lap_time_std_s"])
    if df.empty:
        return _message_figure("Need repeated clean laps to estimate pace consistency.")

    fig = go.Figure()
    for _, row in df.iterrows():
        best_lap_label = _format_lap_time(row["best_clean_lap_s"])
        fig.add_trace(
            go.Scatter(
                x=[row["best_clean_lap_s"]],
                y=[row["lap_time_std_s"]],
                customdata=[best_lap_label],
                mode="markers+text",
                text=[row["driver_label"]],
                textposition="top center",
                marker=dict(
                    size=10,
                    color=row.get("team_color") or "#4da3ff",
                    line=dict(width=1, color="rgba(0,0,0,0.35)"),
                ),
                showlegend=False,
                hovertemplate=(
                    f"Driver: {row['driver_label']}<br>"
                    "Best Clean Lap: %{customdata}<br>"
                    f"Pace Variability: {row['lap_time_std_s']:.3f}s<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        height=430,
        margin=dict(l=8, r=8, t=56, b=30),
        showlegend=False,
    )
    fig.update_xaxes(**_lap_time_axis(df["best_clean_lap_s"], title="Best Clean Lap (mm.ss.SSS)"))
    fig.update_yaxes(title_text="Lap-Time Std Dev (s)", automargin=True)
    return fig


def build_session_specific_live_figures(
    session_category: str,
    position_df: pd.DataFrame,
    pit_lap_df: pd.DataFrame,
    safety_laps: list[int],
    gap_df: pd.DataFrame,
    pace_df: pd.DataFrame,
    bestlap_df: pd.DataFrame,
    speed_df: pd.DataFrame,
    stint_summary_df: pd.DataFrame,
    bestlap_summary_df: pd.DataFrame,
    fastest_lap_row: dict[str, Any] | None,
    is_sprint_session: bool = False,
) -> tuple[go.Figure, go.Figure, go.Figure, dict[str, Any]]:
    profile = _session_profile(session_category, is_sprint_session=is_sprint_session)

    if session_category == "race":
        fig1, fig2, fig3 = build_live_race_figures(
            position_df=position_df,
            pit_lap_df=pit_lap_df,
            safety_laps=safety_laps,
            gap_df=gap_df,
            pace_df=pace_df,
            fastest_lap_row=fastest_lap_row,
            is_sprint_session=is_sprint_session,
        )
    elif session_category == "qualifying":
        fig1, fig2, fig3 = build_live_qualifying_figures(
            bestlap_df=bestlap_df,
            bestlap_summary_df=bestlap_summary_df,
        )
    else:
        fig1, fig2, fig3 = build_live_practice_figures(
            pace_df=pace_df,
            stint_summary_df=stint_summary_df,
            bestlap_summary_df=bestlap_summary_df,
        )

    return fig1, fig2, fig3, profile
