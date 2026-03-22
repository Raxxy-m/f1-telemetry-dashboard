from dash import Input, Output, State, html, ctx, ALL
import plotly.graph_objects as go
import traceback
import pandas as pd
import numpy as np

from services.telemetry_service import (
    prepare_telemetry,
    compute_binary_delta,
)
from services.fastest_lap_service import (
    resolve_fastest_laps,
    build_fastest_lap_table,
    build_fastest_lap_note,
    format_td,
)
from services.kpi_service import compute_comparison_kpi_rows
from services.style_service import extract_driver_styles
from services.session_telemetry_services import (
    prepare_session_laps,
    safe_lap_selection,
    get_lap_telemetry,
    get_lap_time_evolution_data,
)
from figures.telemetry_figure import (
    build_shared_overlay_figure,
)
from figures.track_figure import (
    build_single_driver_track,
    build_binary_delta_track,
    build_multi_driver_message,
)
from figures.mini_track_figure import build_mini_track
from figures.session_telemetry_figure import (
    create_full_session_speed_figure,
    create_lap_delta_to_reference_figure,
)
from figures.lap_time_evolution_figure import create_lap_time_evolution_figure
from figures.comparison_insights_figure import (
    build_cumulative_delta_figure,
    build_sector_delta_figure,
    build_speed_profile_figure,
)

from data_engine import load_session, get_supported_event_schedule, get_live_session_snapshot


OVERLAY_GRAPH_KEYS = ["speed", "throttle", "brake", "rpm", "gear"]
TELEMETRY_STORE_COLUMNS = ["Distance", "Speed", "Throttle", "Brake", "RPM", "nGear", "X", "Y"]


def _serialize_telemetry_for_store(telemetry_df):
    payload = {}
    if telemetry_df is None or telemetry_df.empty:
        return payload

    precision_by_column = {
        "Distance": 1,
        "Speed": 1,
        "Throttle": 1,
        "Brake": 1,
        "RPM": 0,
        "nGear": 0,
        "X": 2,
        "Y": 2,
    }

    for column in TELEMETRY_STORE_COLUMNS:
        if column not in telemetry_df.columns:
            continue
        values = pd.to_numeric(telemetry_df[column], errors="coerce").to_numpy(dtype=float, copy=False)
        rounded = np.round(values, precision_by_column[column])
        payload[column] = [float(val) if np.isfinite(val) else None for val in rounded]
    return payload


def _restore_telemetry_from_store(payload):
    if not payload:
        return pd.DataFrame(columns=TELEMETRY_STORE_COLUMNS)

    restored = {}
    for column in TELEMETRY_STORE_COLUMNS:
        values = payload.get(column)
        if values is None:
            continue
        restored[column] = pd.to_numeric(pd.Series(values), errors="coerce")

    if not restored:
        return pd.DataFrame(columns=TELEMETRY_STORE_COLUMNS)

    df = pd.DataFrame(restored)
    if "Distance" in df.columns:
        df = df.dropna(subset=["Distance"]).sort_values("Distance", kind="mergesort")
        df = df[~df["Distance"].duplicated(keep="first")]
    return df.reset_index(drop=True)


def _blank_fig():
    return go.Figure()


def _message_figure(message, height=360):
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
                font=dict(color="#93a1b5", size=14),
            )
        ],
        margin=dict(l=16, r=16, t=16, b=16),
        height=height,
    )
    return fig


def _metric_card(title, value, detail):
    return html.Div(
        [
            html.Div(title, className="metric-card-title"),
            html.Div(value, className="metric-card-value"),
            html.Div(detail, className="metric-card-detail"),
        ],
        className="metric-card",
    )


def _render_kpi_cards(kpi_rows):
    return [
        _metric_card(row["title"], row["value"], row["detail"])
        for row in kpi_rows
    ]


def _overlay_kpi_cards(session, driver_tel, selected_drivers):
    cards = []
    for driver in selected_drivers:
        if driver not in driver_tel:
            continue

        tel = driver_tel[driver]
        info = session.get_driver(driver)
        abbr = info["Abbreviation"]
        color = info["TeamColor"]
        if not str(color).startswith("#"):
            color = f"#{color}"

        speed = tel["Speed"].dropna()
        throttle = tel["Throttle"].dropna()
        brake = tel["Brake"].dropna()
        gear = tel["nGear"].dropna()

        vmax = float(speed.max()) if not speed.empty else 0.0
        avg_speed = float(speed.mean()) if not speed.empty else 0.0
        throttle_pct = float((throttle >= 98).mean() * 100.0) if not throttle.empty else 0.0

        if not brake.empty:
            brake_binary = (brake > 0).astype(int)
            brake_events = int((brake_binary.diff() == 1).sum())
        else:
            brake_events = 0

        avg_gear = float(gear.mean()) if not gear.empty else 0.0

        cards.append(
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(abbr, className="overlay-kpi-driver"),
                            html.Span(f"({driver})", className="overlay-kpi-driver-id"),
                        ],
                        className="overlay-kpi-head",
                    ),
                    html.Div(
                        [
                            html.Span(f"Vmax {vmax:.1f}", className="overlay-kpi-value"),
                            html.Span(f"Avg {avg_speed:.1f}", className="overlay-kpi-value"),
                            html.Span(f"FullThr {throttle_pct:.1f}%", className="overlay-kpi-value"),
                            html.Span(f"BrkEvt {brake_events}", className="overlay-kpi-value"),
                            html.Span(f"Gear {avg_gear:.2f}", className="overlay-kpi-value"),
                        ],
                        className="overlay-kpi-values",
                    ),
                ],
                className="overlay-kpi-card",
                style={"--driver-color": color},
            )
        )

    return cards


def _with_hash(color_value):
    color_str = str(color_value or "").strip()
    if not color_str:
        return ""
    return color_str if color_str.startswith("#") else f"#{color_str}"


def _fastest_lap_table_styles(table_rows, session):
    styles = [
        {"if": {"column_id": "LapTime"}, "textAlign": "right"},
        {"if": {"column_id": "Sector1"}, "textAlign": "right"},
        {"if": {"column_id": "Sector2"}, "textAlign": "right"},
        {"if": {"column_id": "Sector3"}, "textAlign": "right"},
    ]

    for idx, row in enumerate(table_rows or []):
        driver_code = str(row.get("Driver", ""))
        if driver_code and driver_code in session.drivers:
            team_color = _with_hash(session.get_driver(driver_code).get("TeamColor"))
            if team_color:
                styles.append(
                    {
                        "if": {"row_index": idx, "column_id": "Driver"},
                        "color": team_color,
                        "fontWeight": 700,
                    }
                )

    return styles


def _race_results_table_styles(table_rows):
    styles = [
        {"if": {"column_id": "POS"}, "textAlign": "right"},
        {"if": {"column_id": "PTS"}, "textAlign": "right"},
        {"if": {"column_id": "FINISH DELTA"}, "textAlign": "right"},
        {"if": {"column_id": "BEST LAP"}, "textAlign": "right"},
    ]

    for idx, row in enumerate(table_rows or []):
        team_color = _with_hash(row.get("TEAM_COLOR", ""))
        if team_color:
            styles.append(
                {
                    "if": {"row_index": idx, "column_id": "DRIVER"},
                    "color": team_color,
                    "fontWeight": 700,
                }
            )

    return styles


def _build_race_results_table(session):
    results = getattr(session, "results", None)
    if results is None or results.empty:
        return [], [], "Race classification is unavailable for this session."

    df = results.copy().reset_index(drop=True)
    df["_pos_sort"] = pd.to_numeric(df.get("Position"), errors="coerce").fillna(999.0)
    df = df.sort_values("_pos_sort")

    best_lap_by_driver = {}
    laps = getattr(session, "laps", None)
    if laps is not None and not laps.empty and {"DriverNumber", "LapTime"}.issubset(set(laps.columns)):
        lap_df = laps[["DriverNumber", "LapTime"]].dropna(subset=["DriverNumber", "LapTime"]).copy()
        if not lap_df.empty:
            lap_df["DriverNumber"] = lap_df["DriverNumber"].astype(str)
            best = lap_df.groupby("DriverNumber", as_index=False)["LapTime"].min()
            best_lap_by_driver = {
                str(row["DriverNumber"]): format_td(row["LapTime"])
                for _, row in best.iterrows()
            }

    rows = []
    for _, row in df.iterrows():
        pos_raw = row.get("Position")
        pos_num = pd.to_numeric(pd.Series([pos_raw]), errors="coerce").iloc[0]
        if pd.notna(pos_num):
            pos_label = str(int(pos_num))
        else:
            pos_label = str(pos_raw) if pd.notna(pos_raw) else "--"

        drv_no = str(row.get("DriverNumber", "--"))
        full_name = str(row.get("FullName", "")).strip()
        if not full_name:
            first_name = str(row.get("FirstName", "")).strip()
            last_name = str(row.get("LastName", "")).strip()
            full_name = " ".join(part for part in [first_name, last_name] if part).strip()
        if not full_name:
            full_name = str(row.get("BroadcastName", "")).replace("_", " ").title().strip()
        if not full_name:
            full_name = str(row.get("Abbreviation", drv_no))
        team = str(row.get("TeamName", "--"))
        team_color = ""
        if drv_no in session.drivers:
            team_color = _with_hash(session.get_driver(drv_no).get("TeamColor"))
        if not team_color:
            team_color = _with_hash(row.get("TeamColor", ""))
        points = row.get("Points")

        finish_delta = "--"
        finish_time = row.get("Time")
        status = str(row.get("Status", "")).strip()
        if pos_label == "1":
            finish_delta = "Leader"
        elif pd.notna(finish_time):
            finish_delta = f"+{format_td(finish_time)}"
        elif status:
            finish_delta = status

        best_lap = best_lap_by_driver.get(drv_no, "--")

        rows.append(
            {
                "POS": pos_label,
                "DRIVER": f"{full_name} ({drv_no})",
                "TEAM": team,
                "FINISH DELTA": finish_delta,
                "BEST LAP": best_lap,
                "PTS": f"{float(points):.0f}" if pd.notna(points) else "--",
                "TEAM_COLOR": team_color,
            }
        )

    columns = [{"name": key, "id": key} for key in ["POS", "DRIVER", "TEAM", "FINISH DELTA", "BEST LAP", "PTS"]]
    session_name = str(getattr(session, "name", "") or "")
    if session_name.lower() != "race":
        note = f"Showing classification for selected session: {session_name or 'Unknown'}."
    else:
        note = "Finishing delta is shown as gap to winner where timing data is available."
    return columns, rows, note


def register_callbacks(app):
    @app.callback(
        Output("gp-dd", "options"),
        Output("gp-dd", "value"),
        Input("year-dd", "value"),
        State("gp-dd", "value"),
    )
    def update_gp_dropdown(year, current_gp):
        if not year:
            return [], None

        schedule = get_supported_event_schedule(year)
        options = [
            {
                "label": (
                    f"{row['EventName']} ({row['Location']})"
                    if row["EventFormat"] == "testing"
                    else row["EventName"]
                ),
                "value": int(idx),
            }
            for idx, row in schedule.iterrows()
        ]
        # Always clear selected GP when year changes to avoid stale index mapping.
        return options, None

    @app.callback(
        Output("session-dd", "options"),
        Output("session-dd", "value"),
        Input("year-dd", "value"),
        Input("gp-dd", "value"),
        State("session-dd", "value"),
    )
    def update_sessions(year, gp, current_session):
        if year is None or gp is None:
            return [], None

        schedule = get_supported_event_schedule(year)
        gp_idx = int(gp)
        if gp_idx < 0 or gp_idx >= len(schedule):
            return [], None

        event_row = schedule.iloc[gp_idx]
        options = []

        for idx in range(1, 6):
            col = f"Session{idx}"
            if col not in event_row.index:
                continue
            session_name = event_row[col]
            if pd.isna(session_name):
                continue
            options.append({"label": str(session_name), "value": idx})

        available = {opt["value"] for opt in options}
        next_value = current_session if current_session in available else None
        return options, next_value

    @app.callback(
        Output("archive-session-title", "children"),
        Output("archive-view-context", "children"),
        Output("live-session-detail", "children"),
        Output("live-banner-action", "children"),
        Output("live-banner-action", "disabled"),
        Output("live-banner-action", "className"),
        Output("live-session-store", "data"),
        Input("year-dd", "value"),
        Input("gp-dd", "value"),
        Input("session-dd", "value"),
    )
    def update_archive_context(year, gp, session_type):
        live_snapshot = get_live_session_snapshot()
        
        def live_ui(snapshot):
            if snapshot.get("live"):
                start_utc = str(snapshot.get("session_start_utc", "")).replace("T", " ").replace("+00:00", " UTC")
                return (
                    f"LIVE NOW: {snapshot['year']} / {snapshot['event_name']} / {snapshot['session_name']} "
                    f"(Start: {start_utc})",
                    f"View Live: {snapshot['event_name']} {snapshot['session_name']}",
                    False,
                    "live-banner-action",
                )
            return (
                "No live session right now. Archival view is active.",
                "Archive Mode",
                True,
                "live-banner-action live-banner-action--disabled",
            )

        if year is None:
            live_detail, live_button_text, live_button_disabled, live_button_class = live_ui(live_snapshot)

            return (
                "Select season, event and session",
                "Viewing: -- / -- / --",
                live_detail,
                live_button_text,
                live_button_disabled,
                live_button_class,
                live_snapshot,
            )

        if gp is None:
            title = "Select an event"
            context = f"Viewing: {year} / -- / --"
            live_detail, live_button_text, live_button_disabled, live_button_class = live_ui(live_snapshot)

            return (
                title,
                context,
                live_detail,
                live_button_text,
                live_button_disabled,
                live_button_class,
                live_snapshot,
            )

        schedule = get_supported_event_schedule(year)
        gp_idx = int(gp)
        if gp_idx < 0 or gp_idx >= len(schedule):
            live_detail, live_button_text, live_button_disabled, live_button_class = live_ui(live_snapshot)
            return (
                "Select an event",
                f"Viewing: {year} / -- / --",
                live_detail,
                live_button_text,
                live_button_disabled,
                live_button_class,
                live_snapshot,
            )

        event_row = schedule.iloc[gp_idx]
        event_name = str(event_row["EventName"])

        if session_type is None:
            title = f"{event_name} - Select Session"
            context = f"Viewing: {year} / {event_name} / --"
        else:
            session_label = event_row.get(f"Session{int(session_type)}", f"Session {session_type}")
            if pd.isna(session_label):
                session_label = f"Session {session_type}"
            session_label = str(session_label)

            title = f"{event_name} - {session_label}"
            context = f"Viewing: {year} / {event_name} / {session_label}"

        live_detail, live_button_text, live_button_disabled, live_button_class = live_ui(live_snapshot)

        return (
            title,
            context,
            live_detail,
            live_button_text,
            live_button_disabled,
            live_button_class,
            live_snapshot,
        )

    @app.callback(
        Output("drivers-dd", "options"),
        Output("drivers-dd", "value"),
        Input("year-dd", "value"),
        Input("gp-dd", "value"),
        Input("session-dd", "value"),
        State("drivers-dd", "value"),
    )
    def update_drivers(year, gp, session_type, current_drivers):
        if year is None or gp is None or session_type is None:
            return [], []

        session = load_session(year, int(gp), int(session_type), telemetry=False)
        options = [
            {
                "label": f"{session.get_driver(d)['Abbreviation']} ({d})",
                "value": d,
            }
            for d in session.drivers
        ]
        available = {opt["value"] for opt in options}
        current_drivers = current_drivers or []
        next_drivers = [drv for drv in current_drivers if drv in available]
        return options, next_drivers

    @app.callback(
        Output("lap-driver-buttons", "children"),
        Output("lap-driver-store", "data"),
        Input("year-dd", "value"),
        Input("gp-dd", "value"),
        Input("session-dd", "value"),
        Input("drivers-dd", "value"),
        Input({"type": "lap-driver-btn", "driver": ALL}, "n_clicks"),
        State({"type": "lap-driver-btn", "driver": ALL}, "id"),
        State("lap-driver-store", "data"),
        prevent_initial_call=True,
    )
    def sync_lap_driver_buttons(
        year,
        gp,
        session_type,
        drivers,
        button_clicks,
        button_ids,
        current_lap_driver,
    ):
        if year is None or gp is None or session_type is None or not drivers:
            return [], None

        selected_drivers = drivers if isinstance(drivers, list) else [drivers]
        selected_lookup = {str(driver): driver for driver in selected_drivers}

        trigger = ctx.triggered_id
        if isinstance(trigger, dict) and trigger.get("type") == "lap-driver-btn":
            trigger_driver = selected_lookup.get(str(trigger.get("driver")))
            selected_driver = trigger_driver if trigger_driver is not None else None
        else:
            selected_driver = selected_lookup.get(str(current_lap_driver))

        if selected_driver is None and selected_drivers:
            selected_driver = selected_drivers[0]

        session = load_session(year, int(gp), int(session_type), telemetry=False)
        children = []
        for driver in selected_drivers:
            if driver not in session.drivers:
                continue
            info = session.get_driver(driver)
            color = info["TeamColor"]
            if not str(color).startswith("#"):
                color = f"#{color}"
            abbr = info["Abbreviation"]
            active = driver == selected_driver
            class_name = "lap-driver-btn lap-driver-btn--active" if active else "lap-driver-btn"
            button_style = {
                "--driver-color": color,
                "borderColor": f"{color}66",
                "boxShadow": f"0 0 0 1px {color}22 inset",
            }
            if active:
                button_style.update(
                    {
                        "borderColor": color,
                        "color": "#ffffff",
                        "background": f"linear-gradient(180deg, {color}33, {color}20)",
                        "boxShadow": f"0 0 0 1px {color}55 inset",
                    }
                )
            children.append(
                html.Button(
                    abbr,
                    id={"type": "lap-driver-btn", "driver": driver},
                    n_clicks=0,
                    className=class_name,
                    style=button_style,
                    title=f"{abbr} ({driver})",
                    type="button",
                )
            )

        return children, selected_driver

    @app.callback(
        Output({"type": "overlay-toggle-btn", "graph": ALL}, "className"),
        Output("overlay-toggle-store", "data"),
        Input({"type": "overlay-toggle-btn", "graph": ALL}, "n_clicks"),
        State({"type": "overlay-toggle-btn", "graph": ALL}, "id"),
        State("overlay-toggle-store", "data"),
        prevent_initial_call=True,
    )
    def sync_overlay_toggle_buttons(n_clicks, button_ids, current_selected):
        selected = set(current_selected or OVERLAY_GRAPH_KEYS)
        trigger = ctx.triggered_id

        if isinstance(trigger, dict) and trigger.get("type") == "overlay-toggle-btn":
            graph_key = str(trigger.get("graph"))
            if graph_key in OVERLAY_GRAPH_KEYS:
                if graph_key in selected and len(selected) > 1:
                    selected.remove(graph_key)
                elif graph_key not in selected:
                    selected.add(graph_key)

        ordered_selected = [key for key in OVERLAY_GRAPH_KEYS if key in selected]
        class_list = []
        for button_id in button_ids:
            key = str(button_id.get("graph"))
            if key in ordered_selected:
                class_list.append("overlay-toggle-pill overlay-toggle-pill--active")
            else:
                class_list.append("overlay-toggle-pill overlay-toggle-pill--off")

        return class_list, ordered_selected

    @app.callback(
        Output("telemetry-overlay-graph", "figure"),
        Input("telemetry-store", "data"),
        Input("overlay-toggle-store", "data"),
    )
    def update_shared_overlay_graph(stored_data, visible_graphs):
        if not stored_data or not stored_data.get("telemetry"):
            return _message_figure("Select drivers to render overlay analysis.", height=650)

        telemetry_data = stored_data["telemetry"]
        driver_styles = stored_data.get("styles", {})
        selected_order = stored_data.get("selected_order")
        sector_distances = stored_data.get("sector_distances")

        driver_tel = {drv: _restore_telemetry_from_store(data) for drv, data in telemetry_data.items()}
        return build_shared_overlay_figure(
            driver_tel_dict=driver_tel,
            driver_styles=driver_styles,
            selected_order=selected_order,
            visible_graphs=visible_graphs,
            sector_distances=sector_distances,
        )

    @app.callback(
        Output("overlay-driver-kpis", "children"),
        Output("comparison-kpi-cards", "children"),
        Output("delta-graph", "figure"),
        Output("sector-delta-bars", "figure"),
        Output("speed-profile-graph", "figure"),
        Output("track-delta", "figure"),
        Output("fastest-lap-table", "data"),
        Output("fastest-lap-table", "columns"),
        Output("fastest-lap-table", "style_data_conditional"),
        Output("fastest-lap-note", "children"),
        Output("race-results-table", "data"),
        Output("race-results-table", "columns"),
        Output("race-results-table", "style_data_conditional"),
        Output("race-results-note", "children"),
        Output("debug-output", "children"),
        Output("telemetry-store", "data"),
        Input("year-dd", "value"),
        Input("gp-dd", "value"),
        Input("session-dd", "value"),
        Input("drivers-dd", "value"),
        prevent_initial_call=True,
    )
    def update_dashboard(year, gp, session_type, drivers):
        debug_lines = []
        try:
            debug_lines.append("=== INPUTS ===")
            debug_lines.append(f"Year: {year}")
            debug_lines.append(f"GP: {gp}")
            debug_lines.append(f"Session: {session_type}")
            debug_lines.append(f"Drivers: {drivers}")
            debug_lines.append("")

            if year is None or gp is None or session_type is None or not drivers:
                return (
                    [],
                    _render_kpi_cards(compute_comparison_kpi_rows(None, {}, {})),
                    _blank_fig(),
                    _blank_fig(),
                    _blank_fig(),
                    _blank_fig(),
                    [],
                    [],
                    [],
                    "",
                    [],
                    [],
                    [],
                    "",
                    "\n".join(debug_lines),
                    {},
                )

            session = load_session(year, int(gp), int(session_type), telemetry=True)
            selected_drivers = drivers if isinstance(drivers, list) else [drivers]

            debug_lines.append("Session loaded successfully")
            debug_lines.append(f"Event: {session.event['EventName']}")
            debug_lines.append(f"Total laps: {len(session.laps)}")
            debug_lines.append("")

            fastest_laps, fallback_drivers, selected_drivers = resolve_fastest_laps(
                session,
                selected_drivers,
            )
            driver_tel = {}
            for drv, lap in fastest_laps.items():
                tel = prepare_telemetry(lap)
                driver_tel[drv] = tel
                debug_lines.append(f"{drv}: Telemetry rows = {len(tel)}")

            driver_style = extract_driver_styles(session, selected_drivers)
            store_payload = {
                "telemetry": {
                    drv: _serialize_telemetry_for_store(tel)
                    for drv, tel in driver_tel.items()
                },
                "styles": driver_style,
                "selected_order": selected_drivers,
            }

            reference_driver = next((driver for driver in selected_drivers if driver in fastest_laps), None)
            sector_distances = None
            if reference_driver is not None:
                reference_lap = fastest_laps[reference_driver]
                ref_tel = driver_tel.get(reference_driver)
                s1 = reference_lap["Sector1Time"]
                s2 = reference_lap["Sector2Time"]
                if ref_tel is not None and pd.notna(s1) and pd.notna(s2):
                    sec1 = s1.total_seconds()
                    sec2 = s2.total_seconds()
                    cumulative = ref_tel["Time"].dt.total_seconds()
                    distance = ref_tel["Distance"]
                    if not cumulative.isna().all() and not distance.isna().all():
                        d1 = float(np.interp(sec1, cumulative, distance))
                        d2 = float(np.interp(sec1 + sec2, cumulative, distance))
                        max_d = float(distance.max())
                        if max_d > 0:
                            sector_distances = [max(0.0, d1), max(0.0, d2), max_d]

            store_payload["sector_distances"] = sector_distances
            overlay_kpis = _overlay_kpi_cards(session, driver_tel, selected_drivers)

            delta_fig = build_cumulative_delta_figure(driver_tel, session)
            sector_fig = build_sector_delta_figure(fastest_laps, session)
            speed_profile_fig = build_speed_profile_figure(driver_tel, session)
            kpi_cards = _render_kpi_cards(
                compute_comparison_kpi_rows(session, fastest_laps, driver_tel)
            )

            debug_lines.append(f"Drivers plotted: {len(driver_tel)}")
            debug_lines.append("")

            if len(driver_tel) == 1:
                tel = list(driver_tel.values())[0]
                track_fig = build_single_driver_track(tel)
            elif len(driver_tel) == 2:
                drivers_list = list(driver_tel.keys())
                drv1, drv2 = drivers_list[0], drivers_list[1]
                lap1 = fastest_laps[drv1]
                lap2 = fastest_laps[drv2]
                lap1_time = lap1["LapTime"].total_seconds()
                lap2_time = lap2["LapTime"].total_seconds()

                delta_tel, faster_index = compute_binary_delta(
                    driver_tel[drv1],
                    driver_tel[drv2],
                    lap1_time,
                    lap2_time,
                )

                track_fig = build_binary_delta_track(
                    delta_tel,
                    drv1,
                    drv2,
                    faster_index,
                    session,
                )
            else:
                track_fig = build_multi_driver_message()

            columns, data = build_fastest_lap_table(fastest_laps, selected_drivers)
            fastest_style_conditional = _fastest_lap_table_styles(data, session)
            fastest_lap_note = build_fastest_lap_note(
                session,
                selected_drivers,
                fallback_drivers,
            )
            race_columns, race_data, race_note = _build_race_results_table(session)
            race_style_conditional = _race_results_table_styles(race_data)

            if fallback_drivers:
                fallback_labels = ", ".join(str(drv) for drv in fallback_drivers)
                debug_lines.append(f"Fastest lap fallback used for: {fallback_labels}")
            elif not data:
                debug_lines.append("Fastest lap table empty")
            else:
                debug_lines.append("Fastest lap table populated")

            return (
                overlay_kpis,
                kpi_cards,
                delta_fig,
                sector_fig,
                speed_profile_fig,
                track_fig,
                data,
                columns,
                fastest_style_conditional,
                fastest_lap_note,
                race_data,
                race_columns,
                race_style_conditional,
                race_note,
                "\n".join(debug_lines),
                store_payload,
            )
        except Exception:
            return (
                [],
                _render_kpi_cards(compute_comparison_kpi_rows(None, {}, {})),
                _blank_fig(),
                _blank_fig(),
                _blank_fig(),
                _blank_fig(),
                [],
                [],
                [],
                "",
                [],
                [],
                [],
                "",
                "ERROR:\n" + traceback.format_exc(),
                {},
            )

    @app.callback(
        Output("mini-track-map", "figure"),
        Input("telemetry-overlay-graph", "hoverData"),
        State("telemetry-store", "data"),
    )
    def update_mini_map(hoverData, stored_data):
        if not stored_data:
            return _blank_fig()

        telemetry_data = stored_data["telemetry"]
        driver_styles = stored_data["styles"]
        driver_tel = {drv: _restore_telemetry_from_store(data) for drv, data in telemetry_data.items()}

        reference_distance = None
        if hoverData and "points" in hoverData:
            reference_distance = hoverData["points"][0]["x"]

        return build_mini_track(
            driver_tel=driver_tel,
            driver_styles=driver_styles,
            reference_distance=reference_distance,
        )

    @app.callback(
        Output("lap-input", "max"),
        Output("lap-max-label", "children"),
        Input("year-dd", "value"),
        Input("gp-dd", "value"),
        Input("session-dd", "value"),
        Input("lap-driver-store", "data"),
        prevent_initial_call=True,
    )
    def update_lap_slider(year, gp, session_name, lap_driver):
        if year is None or gp is None or session_name is None or lap_driver is None:
            return 1, "/ 1 laps"

        session = load_session(year, int(gp), int(session_name), telemetry=False)
        laps = prepare_session_laps(
            session=session,
            driver_code=lap_driver,
            valid_only=True,
        )

        if laps.empty:
            return 1, "/ 1 laps"

        max_lap = int(laps["LapNumber"].max())
        return max_lap, f"/ {max_lap} laps"

    @app.callback(
        Output("lap-input", "value"),
        Input("lap-input", "value"),
        Input("lap-prev-btn", "n_clicks"),
        Input("lap-next-btn", "n_clicks"),
        Input("lap-input", "max"),
        Input("year-dd", "value"),
        Input("gp-dd", "value"),
        Input("session-dd", "value"),
        Input("lap-driver-store", "data"),
        prevent_initial_call=True,
    )
    def sync_lap_controls(
        input_value,
        prev_clicks,
        next_clicks,
        max_lap,
        year,
        gp,
        session_name,
        lap_driver,
    ):
        max_lap = int(max_lap or 1)
        trigger_prop = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
        trigger = ctx.triggered_id

        current_value = int(input_value or 1)

        if trigger_prop in {
            "year-dd.value",
            "gp-dd.value",
            "session-dd.value",
            "lap-driver-store.data",
        }:
            next_value = 1
        elif trigger == "lap-prev-btn":
            next_value = current_value - 1
        elif trigger == "lap-next-btn":
            next_value = current_value + 1
        elif trigger == "lap-input":
            next_value = int(input_value or current_value)
        elif trigger_prop == "lap-input.max":
            next_value = current_value
        else:
            next_value = current_value

        next_value = max(1, min(max_lap, next_value))
        return next_value

    @app.callback(
        Output("full-session-telemetry-graph", "figure"),
        Output("lap-delta-fastest-graph", "figure"),
        Output("lap-context", "children"),
        Input("lap-input", "value"),
        Input("year-dd", "value"),
        Input("gp-dd", "value"),
        Input("session-dd", "value"),
        Input("lap-driver-store", "data"),
        prevent_initial_call=True,
    )
    def update_full_session_graph(
        lap_number,
        year,
        gp,
        session_name,
        lap_driver,
    ):
        if (
            lap_number is None
            or year is None
            or gp is None
            or session_name is None
            or lap_driver is None
        ):
            return (
                _message_figure("Select 1 driver to view lap telemetry drilldown.", height=760),
                _message_figure("Select 1 driver to compute lap delta to this driver's best lap.", height=420),
                [html.Span("Awaiting session + driver selection.", className="lap-context-item")],
            )
        driver = lap_driver
        session = load_session(year, int(gp), int(session_name), telemetry=True)
        laps = prepare_session_laps(
            session=session,
            driver_code=driver,
            valid_only=True,
        )

        if laps.empty:
            return (
                _message_figure("No valid laps available for selected driver.", height=760),
                _message_figure("No valid laps available for selected driver.", height=420),
                [html.Span("No valid lap data in this session.", className="lap-context-item")],
            )

        selected_lap = safe_lap_selection(laps, lap_number)
        selected_lap_number = int(selected_lap["LapNumber"])
        selected_telemetry = get_lap_telemetry(selected_lap)

        fastest_lap = laps.loc[laps["LapTime"].idxmin()]
        fastest_lap_number = int(fastest_lap["LapNumber"])
        fastest_telemetry = get_lap_telemetry(fastest_lap)

        full_session_fig = create_full_session_speed_figure(
            telemetry=selected_telemetry,
            driver=driver,
            lap_number=selected_lap_number,
            reference_telemetry=fastest_telemetry,
            reference_lap_number=fastest_lap_number,
            session=session,
        )

        delta_fig = create_lap_delta_to_reference_figure(
            telemetry=selected_telemetry,
            reference_telemetry=fastest_telemetry,
            driver=driver,
            lap_number=selected_lap_number,
            reference_lap_number=fastest_lap_number,
            session=session,
        )

        selected_time_s = selected_lap["LapTime"].total_seconds()
        fastest_time_s = fastest_lap["LapTime"].total_seconds()
        delta_to_fastest = selected_time_s - fastest_time_s
        sign = "+" if delta_to_fastest >= 0 else "-"

        session_best_lap = None
        session_laps = session.laps[
            session.laps["LapTime"].notna()
            & session.laps["PitInTime"].isna()
            & session.laps["PitOutTime"].isna()
        ]
        if "Deleted" in session_laps.columns:
            session_laps = session_laps[session_laps["Deleted"] == False]
        if not session_laps.empty:
            session_best_lap = session_laps.loc[session_laps["LapTime"].idxmin()]

        team_color = session.get_driver(driver)["TeamColor"]
        if not str(team_color).startswith("#"):
            team_color = f"#{team_color}"

        context = [
            html.Span(
                f"Driver: {session.get_driver(driver)['Abbreviation']} ({driver})",
                className="lap-context-item",
                style={
                    "borderColor": f"{team_color}88",
                    "boxShadow": f"0 0 0 1px {team_color}22 inset",
                },
            ),
            html.Span(
                f"Selected Lap {selected_lap_number}: {format_td(selected_lap['LapTime'])}",
                className="lap-context-item",
                style={
                    "borderColor": f"{team_color}66",
                },
            ),
            html.Span(
                f"Driver Best Lap {fastest_lap_number}: {format_td(fastest_lap['LapTime'])}",
                className="lap-context-item",
            ),
            html.Span(
                f"Delta to driver best: {sign}{abs(delta_to_fastest):.3f}s",
                className="lap-context-item lap-context-item--accent",
                style={
                    "borderColor": f"{team_color}aa",
                    "background": f"linear-gradient(180deg, {team_color}2b, {team_color}18)",
                    "color": "#ffffff",
                },
            ),
        ]

        if session_best_lap is not None:
            session_best_time = session_best_lap["LapTime"].total_seconds()
            delta_to_session_best = selected_time_s - session_best_time
            session_sign = "+" if delta_to_session_best >= 0 else "-"
            context.append(
                html.Span(
                    f"Delta to session best: {session_sign}{abs(delta_to_session_best):.3f}s",
                    className="lap-context-item",
                )
            )

        return full_session_fig, delta_fig, context

    @app.callback(
        Output("lap-time-evolution-graph", "figure"),
        Input("year-dd", "value"),
        Input("gp-dd", "value"),
        Input("session-dd", "value"),
        Input("drivers-dd", "value"),
        prevent_initial_call=True,
    )
    def update_lap_time_evolution(year, gp, session_name, drivers):
        if year is None or gp is None or session_name is None or not drivers:
            return _message_figure("Select up to 2 drivers for lap-time evolution.", height=420)

        if not isinstance(drivers, list):
            return _message_figure("Select up to 2 drivers for lap-time evolution.", height=420)

        if len(drivers) > 2:
            return _message_figure("Select up to 2 drivers for lap-time evolution comparison.", height=420)

        session = load_session(year, int(gp), int(session_name), telemetry=False)
        payloads = []
        for driver in drivers:
            laps = session.laps.pick_drivers(driver)
            if laps.empty:
                continue
            df, fastest_idx = get_lap_time_evolution_data(laps)
            payloads.append(
                {
                    "driver": driver,
                    "df": df,
                    "fastest_idx": fastest_idx,
                }
            )

        if not payloads:
            return _message_figure("No lap data available for selected drivers.", height=420)

        return create_lap_time_evolution_figure(payloads, session)
