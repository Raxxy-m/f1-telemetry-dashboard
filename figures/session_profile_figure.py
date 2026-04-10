import numpy as np
import pandas as pd
import plotly.graph_objects as go
from fastf1.plotting import get_driver_style

from theme import COLORS, apply_standard_hover_layout


def _message_figure(message, height=320):
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
        margin=dict(l=12, r=12, t=16, b=12),
        height=height,
    )
    return fig


def _driver_meta(session, driver):
    info = session.get_driver(driver)
    abbr = info["Abbreviation"]
    color = get_driver_style(abbr, style=["color"], session=session)["color"]
    return abbr, color


def _valid_driver_laps(session, driver):
    laps = session.laps.pick_drivers(driver).copy()
    if laps.empty:
        return laps

    laps = laps[
        laps["LapTime"].notna()
        & laps["PitInTime"].isna()
        & laps["PitOutTime"].isna()
    ].copy()

    if "Deleted" in laps.columns:
        laps = laps[laps["Deleted"] == False].copy()

    if not laps.empty:
        laps["LapTimeSeconds"] = laps["LapTime"].dt.total_seconds()
    return laps


def build_tyre_degradation_figure(session, selected_drivers):
    if not selected_drivers:
        return _message_figure("Select one or more drivers to render tyre degradation trend.", height=360)

    fig = go.Figure()
    plotted = 0
    uses_tyre_life = False
    dash_styles = ["solid", "dot", "dash", "longdash"]

    for driver in selected_drivers:
        laps = _valid_driver_laps(session, driver)
        if laps.empty:
            continue

        abbr, color = _driver_meta(session, driver)
        x_col = "TyreLife" if "TyreLife" in laps.columns and laps["TyreLife"].notna().any() else "LapNumber"
        uses_tyre_life = uses_tyre_life or x_col == "TyreLife"

        if "Stint" in laps.columns and laps["Stint"].notna().any():
            stint_groups = list(laps.sort_values([x_col, "LapNumber"]).groupby("Stint", sort=True))
        else:
            stint_groups = [(1, laps.sort_values([x_col, "LapNumber"]))]

        for idx, (stint, stint_df) in enumerate(stint_groups):
            stint_df = stint_df.dropna(subset=[x_col, "LapTimeSeconds"])
            if len(stint_df) < 2:
                continue

            compound_series = (
                stint_df["Compound"].fillna("-")
                if "Compound" in stint_df.columns
                else pd.Series(["-"] * len(stint_df), index=stint_df.index)
            )
            compound = "-"
            if "Compound" in stint_df.columns:
                mode = compound_series.dropna().mode()
                if not mode.empty:
                    compound = str(mode.iloc[0])

            fig.add_trace(
                go.Scatter(
                    x=stint_df[x_col],
                    y=stint_df["LapTimeSeconds"],
                    mode="markers+lines",
                    name=f"{abbr} S{int(stint)} ({compound})",
                    line=dict(color=color, width=2.0, dash=dash_styles[idx % len(dash_styles)]),
                    marker=dict(size=6, color=color, opacity=0.9),
                    hovertemplate=(
                        f"{abbr} | Stint {int(stint)}<br>"
                        f"{x_col}: %{{x}}<br>"
                        "Lap: %{customdata[0]}<br>"
                        "Time: %{y:.3f}s<br>"
                        "Compound: %{customdata[1]}<extra></extra>"
                    ),
                    customdata=np.column_stack(
                        [
                            stint_df["LapNumber"].fillna(-1).astype(int),
                            compound_series,
                        ]
                    ),
                )
            )
            plotted += 1

    if plotted == 0:
        return _message_figure("Insufficient stint data for tyre degradation trend.", height=360)

    fig = apply_standard_hover_layout(fig)
    fig.update_layout(
        title=dict(text="Tyre Degradation by Stint", x=0.5, xanchor="center"),
        margin=dict(l=56, r=18, t=70, b=58),
        height=360,
        legend=dict(orientation="h", y=1.02, x=0),
    )
    fig.update_xaxes(title_text="Tyre Life (laps)" if uses_tyre_life else "Lap Number", automargin=True)
    fig.update_yaxes(title_text="Lap Time (s)", automargin=True)
    return fig


def build_minisector_delta_figure(driver_tel_dict, session, fastest_laps=None):
    if len(driver_tel_dict) != 2:
        return _message_figure("Select exactly 2 drivers to compare mini-sector deltas.", height=320)

    driver_1, driver_2 = list(driver_tel_dict.keys())
    tel_1 = driver_tel_dict[driver_1].sort_values("Distance").copy()
    tel_2 = driver_tel_dict[driver_2].sort_values("Distance").copy()

    max_distance = min(tel_1["Distance"].max(), tel_2["Distance"].max())
    if np.isnan(max_distance) or max_distance <= 0:
        return _message_figure("Telemetry distance data unavailable for mini-sector delta.", height=320)

    abbr_1, color_1 = _driver_meta(session, driver_1)
    abbr_2, color_2 = _driver_meta(session, driver_2)

    distance_axis = np.linspace(0, max_distance, 1600)
    t1 = np.interp(distance_axis, tel_1["Distance"], tel_1["Time"].dt.total_seconds())
    t2 = np.interp(distance_axis, tel_2["Distance"], tel_2["Time"].dt.total_seconds())
    delta = t2 - t1

    bins = int(np.clip(max_distance / 150.0, 12, 40))
    edges = np.linspace(0.0, max_distance, bins + 1)
    centers = (edges[:-1] + edges[1:]) * 0.5

    mini_delta = []
    for idx in range(bins):
        left = edges[idx]
        right = edges[idx + 1]
        mask = (distance_axis >= left) & (distance_axis < right)
        if not np.any(mask):
            mini_delta.append(np.nan)
        else:
            mini_delta.append(float(np.nanmean(delta[mask])))

    mini_delta = np.array(mini_delta, dtype=float)
    if np.all(np.isnan(mini_delta)):
        return _message_figure("Unable to compute mini-sector delta for selected laps.", height=320)

    colors = np.where(mini_delta >= 0, color_1, color_2)
    labels = np.arange(1, bins + 1)

    fig = go.Figure(
        go.Bar(
            x=labels,
            y=mini_delta,
            marker=dict(color=colors),
            width=0.9,
            customdata=np.column_stack([centers, edges[:-1], edges[1:]]),
            hovertemplate=(
                "Mini-sector %{x}<br>"
                "Track: %{customdata[1]:.0f}m - %{customdata[2]:.0f}m<br>"
                f"Delta ({abbr_2} - {abbr_1}): %{{y:+.3f}}s<extra></extra>"
            ),
        )
    )

    fig.add_hline(y=0, line_width=1, line_dash="dot", line_color=COLORS["border_strong"])
    fig = apply_standard_hover_layout(fig)
    fig.update_layout(
        title=dict(text="Mini-Sector Delta by Distance", x=0.5, xanchor="center"),
        margin=dict(l=56, r=18, t=76, b=54),
        height=320,
        showlegend=False,
    )
    fig.update_xaxes(title_text="Mini-sector Index", automargin=True)
    fig.update_yaxes(title_text=f"Delta (s) | + = {abbr_1} gain", automargin=True)
    return fig


def build_stint_pace_figure(session, selected_drivers):
    if not selected_drivers:
        return _message_figure("Select drivers to compare stint pace.", height=320)

    rows = []
    for driver in selected_drivers:
        laps = _valid_driver_laps(session, driver)
        if laps.empty:
            continue

        if "Stint" not in laps.columns or not laps["Stint"].notna().any():
            laps["Stint"] = 1

        abbr, _ = _driver_meta(session, driver)
        for stint, stint_df in laps.groupby("Stint", sort=True):
            stint_df = stint_df.sort_values("LapNumber")
            if stint_df.empty:
                continue

            avg_pace = float(stint_df["LapTimeSeconds"].mean())
            lap_count = int(len(stint_df))
            trend = np.nan
            if lap_count >= 2:
                x = np.arange(lap_count, dtype=float)
                trend = float(np.polyfit(x, stint_df["LapTimeSeconds"].to_numpy(dtype=float), 1)[0])

            compound = "-"
            if "Compound" in stint_df.columns:
                mode = stint_df["Compound"].dropna().mode()
                if not mode.empty:
                    compound = str(mode.iloc[0])

            rows.append(
                {
                    "driver": driver,
                    "abbr": abbr,
                    "stint": int(stint),
                    "avg_pace": avg_pace,
                    "lap_count": lap_count,
                    "trend": trend,
                    "compound": compound,
                }
            )

    if not rows:
        return _message_figure("No valid stint data available.", height=320)

    df = pd.DataFrame(rows).sort_values(["stint", "abbr"])
    fig = go.Figure()
    for driver in df["driver"].unique():
        drv_df = df[df["driver"] == driver]
        abbr, color = _driver_meta(session, driver)
        fig.add_trace(
            go.Bar(
                x=[f"S{int(val)}" for val in drv_df["stint"]],
                y=drv_df["avg_pace"],
                name=abbr,
                marker=dict(color=color),
                customdata=np.column_stack(
                    [
                        drv_df["lap_count"],
                        drv_df["compound"],
                        np.nan_to_num(drv_df["trend"], nan=0.0),
                    ]
                ),
                hovertemplate=(
                    f"{abbr}<br>"
                    "Stint: %{x}<br>"
                    "Avg Pace: %{y:.3f}s<br>"
                    "Laps: %{customdata[0]}<br>"
                    "Compound: %{customdata[1]}<br>"
                    "Trend: %{customdata[2]:+.3f}s/lap<extra></extra>"
                ),
            )
        )

    fig = apply_standard_hover_layout(fig)
    fig.update_layout(
        title=dict(text="Stint Pace Summary", x=0.5, xanchor="center"),
        barmode="group",
        margin=dict(l=56, r=18, t=70, b=52),
        height=320,
        legend=dict(orientation="h", y=1.02, x=0),
    )
    fig.update_xaxes(title_text="Stint", automargin=True)
    fig.update_yaxes(title_text="Average Lap Time (s)", automargin=True)
    return fig


def build_corner_loss_figure(driver_tel_dict, session):
    if len(driver_tel_dict) != 2:
        return _message_figure("Select exactly 2 drivers to map corner gain/loss.", height=360)

    driver_1, driver_2 = list(driver_tel_dict.keys())
    tel_1 = driver_tel_dict[driver_1].sort_values("Distance").copy()
    tel_2 = driver_tel_dict[driver_2].sort_values("Distance").copy()

    max_distance = min(tel_1["Distance"].max(), tel_2["Distance"].max())
    if np.isnan(max_distance) or max_distance <= 0:
        return _message_figure("Telemetry distance data unavailable for corner mapping.", height=360)

    abbr_1, color_1 = _driver_meta(session, driver_1)
    abbr_2, color_2 = _driver_meta(session, driver_2)

    distance_axis = np.linspace(0, max_distance, 1700)
    t1 = np.interp(distance_axis, tel_1["Distance"], tel_1["Time"].dt.total_seconds())
    t2 = np.interp(distance_axis, tel_2["Distance"], tel_2["Time"].dt.total_seconds())
    delta = t2 - t1

    brake_1 = np.interp(distance_axis, tel_1["Distance"], tel_1["Brake"].fillna(0.0).to_numpy(dtype=float))
    brake_2 = np.interp(distance_axis, tel_2["Distance"], tel_2["Brake"].fillna(0.0).to_numpy(dtype=float))
    brake_max = np.maximum(brake_1, brake_2)

    in_brake_zone = brake_max > 35.0
    braking_entries = np.where((~in_brake_zone[:-1]) & (in_brake_zone[1:]))[0] + 1

    boundaries = [0.0]
    for idx in braking_entries:
        boundaries.append(float(distance_axis[idx]))
    boundaries.append(float(max_distance))
    boundaries = sorted(set(boundaries))

    if len(boundaries) < 4:
        boundaries = list(np.linspace(0.0, float(max_distance), 13))

    segments = []
    for idx in range(len(boundaries) - 1):
        start_d = boundaries[idx]
        end_d = boundaries[idx + 1]
        if end_d - start_d < 35:
            continue

        start_i = int(np.searchsorted(distance_axis, start_d))
        end_i = int(np.searchsorted(distance_axis, end_d))
        if end_i <= start_i:
            continue

        seg_delta = float(delta[end_i] - delta[start_i])
        center_d = 0.5 * (start_d + end_d)
        segments.append(
            {
                "label": f"C{idx + 1}",
                "delta": seg_delta,
                "center": center_d,
            }
        )

    if not segments:
        return _message_figure("Unable to derive corner-level deltas for selected laps.", height=360)

    seg_df = pd.DataFrame(segments)
    seg_df["abs_delta"] = seg_df["delta"].abs()
    seg_df = seg_df.sort_values("abs_delta", ascending=False).head(10).sort_values("center")
    seg_df["color"] = np.where(seg_df["delta"] >= 0, color_1, color_2)

    fig = go.Figure(
        go.Bar(
            x=seg_df["delta"],
            y=seg_df["label"],
            orientation="h",
            marker=dict(color=seg_df["color"]),
            text=[f"{val:+.3f}s" for val in seg_df["delta"]],
            textposition="auto",
            customdata=np.column_stack([seg_df["center"]]),
            hovertemplate=(
                "Segment: %{y}<br>"
                "Track Position: %{customdata[0]:.0f}m<br>"
                f"Delta Change ({abbr_2} - {abbr_1}): %{{x:+.3f}}s<extra></extra>"
            ),
        )
    )

    fig.add_vline(x=0, line_width=1, line_dash="dot", line_color=COLORS["border_strong"])
    fig = apply_standard_hover_layout(fig)
    fig.update_layout(
        title=dict(text="Corner Gain/Loss Hotspots", x=0.5, xanchor="center"),
        margin=dict(l=88, r=20, t=72, b=54),
        height=360,
        showlegend=False,
    )
    fig.update_xaxes(title_text=f"Segment Delta (s) | + = {abbr_1} gain", automargin=True)
    fig.update_yaxes(autorange="reversed", automargin=True)
    return fig
