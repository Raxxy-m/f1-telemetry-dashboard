from collections import defaultdict

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from theme import COLORS, apply_standard_hover_layout


GRAPH_ORDER = ["speed", "throttle", "brake", "rpm", "gear"]

GRAPH_META = {
    "speed": {
        "title": "Speed",
        "column": "Speed",
        "y_label": "Speed (km/h)",
        "line_width": 2.5,
        "hover_fmt": ".1f",
        "shape": None,
        "fill": False,
        "weight": 3.2,
    },
    "throttle": {
        "title": "Throttle",
        "column": "Throttle",
        "y_label": "Throttle (%)",
        "line_width": 1.8,
        "hover_fmt": ".0f",
        "shape": None,
        "fill": False,
        "weight": 1.55,
        "range": [0, 100],
        "hide_grid": True,
    },
    "brake": {
        "title": "Brake",
        "column": "Brake",
        "y_label": "Brake (%)",
        "line_width": 1.45,
        "hover_fmt": ".0f",
        "shape": "hv",
        "fill": True,
        "weight": 1.45,
        "range": [0, 100],
        "hide_grid": True,
    },
    "rpm": {
        "title": "RPM",
        "column": "RPM",
        "y_label": "RPM",
        "line_width": 1.85,
        "hover_fmt": ".0f",
        "shape": None,
        "fill": False,
        "weight": 1.45,
    },
    "gear": {
        "title": "Gear",
        "column": "nGear",
        "y_label": "Gear",
        "line_width": 1.7,
        "hover_fmt": ".0f",
        "shape": "hv",
        "fill": False,
        "weight": 1.2,
        "range": [0.5, 8.5],
        "dtick": 1,
        "hide_grid": True,
    },
}


def _message_figure(message, height=650):
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
                font=dict(color=COLORS["text_tertiary"], size=14),
            )
        ],
        margin=dict(l=20, r=20, t=20, b=20),
        height=height,
    )
    return fig


def _ordered_drivers(driver_tel_dict, selected_order):
    if selected_order:
        ordered = [driver for driver in selected_order if driver in driver_tel_dict]
        if ordered:
            return ordered
    return list(driver_tel_dict.keys())


def _build_dash_map(driver_styles, ordered_drivers):
    team_counts = defaultdict(int)
    dash_map = {}

    for driver in ordered_drivers:
        color = str(driver_styles.get(driver, {}).get("color", COLORS["telemetry_2"])).lower()
        team_counts[color] += 1
        dash_map[driver] = "dot" if team_counts[color] >= 2 else "solid"

    return dash_map


def _apply_sector_guides(fig, rows, sector_distances):
    if not sector_distances:
        return

    d1, d2, max_distance = sector_distances
    zones = [
        (0.0, d1, "rgba(255, 255, 255, 0.016)"),
        (d1, d2, "rgba(255, 255, 255, 0.028)"),
        (d2, max_distance, "rgba(255, 255, 255, 0.016)"),
    ]

    for row in range(1, rows + 1):
        for x0, x1, fill_color in zones:
            fig.add_vrect(
                x0=x0,
                x1=x1,
                fillcolor=fill_color,
                opacity=1,
                line_width=0,
                layer="below",
                row=row,
                col=1,
            )

        fig.add_vline(
            x=d1,
            line_width=1,
            line_dash="dot",
            line_color="rgba(147, 161, 181, 0.52)",
            row=row,
            col=1,
        )
        fig.add_vline(
            x=d2,
            line_width=1,
            line_dash="dot",
            line_color="rgba(147, 161, 181, 0.52)",
            row=row,
            col=1,
        )

    fig.add_annotation(
        x=d1 / 2,
        y=1.015,
        text="S1",
        xref="x",
        yref="paper",
        showarrow=False,
        font=dict(size=10, color=COLORS["text_tertiary"]),
    )
    fig.add_annotation(
        x=(d1 + d2) / 2,
        y=1.015,
        text="S2",
        xref="x",
        yref="paper",
        showarrow=False,
        font=dict(size=10, color=COLORS["text_tertiary"]),
    )
    fig.add_annotation(
        x=(d2 + max_distance) / 2,
        y=1.015,
        text="S3",
        xref="x",
        yref="paper",
        showarrow=False,
        font=dict(size=10, color=COLORS["text_tertiary"]),
    )


def build_shared_overlay_figure(
    driver_tel_dict,
    driver_styles,
    selected_order=None,
    visible_graphs=None,
    sector_distances=None,
):
    if not driver_tel_dict:
        return _message_figure("Select drivers to render overlay analysis.")

    visible_set = set(visible_graphs or GRAPH_ORDER)
    active_graphs = [key for key in GRAPH_ORDER if key in visible_set]
    if not active_graphs:
        active_graphs = ["speed"]

    ordered_drivers = _ordered_drivers(driver_tel_dict, selected_order)
    if not ordered_drivers:
        return _message_figure("No telemetry available for selected drivers.")

    row_weights = [GRAPH_META[key]["weight"] for key in active_graphs]
    total_weight = float(sum(row_weights)) or 1.0
    row_heights = [weight / total_weight for weight in row_weights]

    fig = make_subplots(
        rows=len(active_graphs),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.016,
        row_heights=row_heights,
    )

    dash_map = _build_dash_map(driver_styles, ordered_drivers)
    first_row_key = active_graphs[0]

    for row_idx, graph_key in enumerate(active_graphs, start=1):
        graph_meta = GRAPH_META[graph_key]

        for driver in ordered_drivers:
            tel = driver_tel_dict[driver]
            style = driver_styles.get(driver, {})
            color = style.get("color", COLORS["telemetry_2"])
            label = style.get("label", str(driver))
            dash = dash_map.get(driver, "solid")

            trace_kwargs = dict(
                x=tel["Distance"],
                y=tel[graph_meta["column"]],
                mode="lines",
                name=label,
                line=dict(color=color, width=graph_meta["line_width"], dash=dash),
                showlegend=(graph_key == first_row_key),
                hovertemplate=(
                    f"{label}<br>"
                    "Distance: %{x:.0f} m<br>"
                    f"{graph_meta['y_label']}: %{{y:{graph_meta['hover_fmt']}}}<extra></extra>"
                ),
            )

            if graph_meta.get("shape"):
                trace_kwargs["line"]["shape"] = graph_meta["shape"]
            if graph_meta.get("fill"):
                trace_kwargs["fill"] = "tozeroy"
                trace_kwargs["opacity"] = 0.18 if len(ordered_drivers) > 1 else 0.24

            fig.add_trace(go.Scattergl(**trace_kwargs), row=row_idx, col=1)

        fig.update_yaxes(title_text=graph_meta["y_label"], row=row_idx, col=1)
        if "range" in graph_meta:
            fig.update_yaxes(range=graph_meta["range"], row=row_idx, col=1)
        if graph_meta.get("dtick"):
            fig.update_yaxes(dtick=graph_meta["dtick"], row=row_idx, col=1)
        if graph_meta.get("hide_grid"):
            fig.update_yaxes(showgrid=False, row=row_idx, col=1)

    # Robust RPM scaling if row is active.
    if "rpm" in active_graphs:
        rpm_row = active_graphs.index("rpm") + 1
        rpm_values = []
        for driver in ordered_drivers:
            vals = driver_tel_dict[driver]["RPM"].dropna().to_numpy()
            if vals.size > 0:
                rpm_values.append(vals)

        if rpm_values:
            values = np.concatenate(rpm_values)
            values = values[np.isfinite(values)]
            if values.size > 0:
                q05 = float(np.percentile(values, 5))
                q95 = float(np.percentile(values, 95))
                lower = max(4500.0, np.floor((q05 - 400.0) / 250.0) * 250.0)
                upper = np.ceil((q95 + 650.0) / 250.0) * 250.0
                if upper - lower < 2000:
                    upper = lower + 2000
                fig.update_yaxes(range=[lower, upper], row=rpm_row, col=1)

    _apply_sector_guides(fig, len(active_graphs), sector_distances)

    fig = apply_standard_hover_layout(fig)
    figure_height = int(240 + 82 * len(active_graphs))
    title_parts = [GRAPH_META[key]["title"] for key in active_graphs]
    fig.update_layout(
        title=dict(
            text="Telemetry Overlay | " + " / ".join(title_parts),
            x=0.5,
            xanchor="center",
            font=dict(size=16, color=COLORS["text_primary"]),
        ),
        height=max(520, figure_height),
        margin=dict(l=58, r=18, t=74, b=54),
        legend=dict(
            orientation="h",
            y=0.995,
            x=0.01,
            yanchor="top",
            xanchor="left",
            bgcolor="rgba(17, 23, 34, 0.52)",
        ),
    )

    last_row = len(active_graphs)
    fig.update_xaxes(
        title_text="Distance (m)",
        row=last_row,
        col=1,
        gridcolor=COLORS["grid"],
        automargin=True,
    )
    fig.update_xaxes(gridcolor=COLORS["grid"])
    fig.update_yaxes(gridcolor=COLORS["grid"])
    return fig
