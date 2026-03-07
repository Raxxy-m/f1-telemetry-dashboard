from dash import Input, Output, State, html, ctx
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go
import traceback
import pandas as pd

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
from services.session_telemetry_services import (
    prepare_session_laps,
    safe_lap_selection,
    get_lap_telemetry,
    get_lap_time_evolution_data,
)
from services.telemetry_provider import telemetry_provider
from figures.telemetry_figure import build_telemetry_figure
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
from figures.live_session_figure import build_session_specific_live_figures


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

        schedule = telemetry_provider.get_supported_event_schedule(year)
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

        schedule = telemetry_provider.get_supported_event_schedule(year)
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

        session = telemetry_provider.load_historical_session(year, int(gp), int(session_type))
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
        Output("telemetry-graph", "figure"),
        Output("comparison-kpi-cards", "children"),
        Output("delta-graph", "figure"),
        Output("sector-delta-bars", "figure"),
        Output("speed-profile-graph", "figure"),
        Output("track-delta", "figure"),
        Output("fastest-lap-table", "data"),
        Output("fastest-lap-table", "columns"),
        Output("fastest-lap-note", "children"),
        Output("debug-output", "children"),
        Output("telemetry-store", "data"),
        Input("year-dd", "value"),
        Input("gp-dd", "value"),
        Input("session-dd", "value"),
        Input("drivers-dd", "value"),
        Input("view-tabs", "value"),
        prevent_initial_call=True,
    )
    def update_dashboard(year, gp, session_type, drivers, active_tab):
        if active_tab != "performance-comparison-tab":
            raise PreventUpdate

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
                    _blank_fig(),
                    _render_kpi_cards(compute_comparison_kpi_rows(None, {}, {})),
                    _blank_fig(),
                    _blank_fig(),
                    _blank_fig(),
                    _blank_fig(),
                    [],
                    [],
                    "",
                    "\n".join(debug_lines),
                    {},
                )

            session = telemetry_provider.load_historical_session(year, int(gp), int(session_type))
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

            driver_style = telemetry_provider.get_driver_styles(session, drivers)

            store_payload = {
                "telemetry": {
                    drv: tel.to_dict("records")
                    for drv, tel in driver_tel.items()
                },
                "styles": driver_style,
            }

            telemetry_fig = build_telemetry_figure(driver_tel, session)
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
            fastest_lap_note = build_fastest_lap_note(
                session,
                selected_drivers,
                fallback_drivers,
            )

            if fallback_drivers:
                fallback_labels = ", ".join(str(drv) for drv in fallback_drivers)
                debug_lines.append(f"Fastest lap fallback used for: {fallback_labels}")
            elif not data:
                debug_lines.append("Fastest lap table empty")
            else:
                debug_lines.append("Fastest lap table populated")

            return (
                telemetry_fig,
                kpi_cards,
                delta_fig,
                sector_fig,
                speed_profile_fig,
                track_fig,
                data,
                columns,
                fastest_lap_note,
                "\n".join(debug_lines),
                store_payload,
            )
        except Exception:
            return (
                _blank_fig(),
                _render_kpi_cards(compute_comparison_kpi_rows(None, {}, {})),
                _blank_fig(),
                _blank_fig(),
                _blank_fig(),
                _blank_fig(),
                [],
                [],
                "",
                "ERROR:\n" + traceback.format_exc(),
                {},
            )

    @app.callback(
        Output("mini-track-map", "figure"),
        Input("telemetry-graph", "hoverData"),
        Input("view-tabs", "value"),
        State("telemetry-store", "data"),
    )
    def update_mini_map(hoverData, active_tab, stored_data):
        if active_tab != "performance-comparison-tab":
            raise PreventUpdate

        if not stored_data:
            return _blank_fig()

        telemetry_data = stored_data["telemetry"]
        driver_styles = stored_data["styles"]
        driver_tel = {drv: pd.DataFrame(data) for drv, data in telemetry_data.items()}

        reference_distance = None
        if hoverData and "points" in hoverData:
            reference_distance = hoverData["points"][0]["x"]

        return build_mini_track(
            driver_tel=driver_tel,
            driver_styles=driver_styles,
            reference_distance=reference_distance,
        )

    @app.callback(
        Output("performance-tab-content", "style"),
        Output("session-tab-content", "style"),
        Output("live-tab-content", "style"),
        Output("global-filter-container", "style"),
        Output("debug-output", "style"),
        Input("view-tabs", "value"),
    )
    def toggle_tabs(tab):
        if tab == "performance-comparison-tab":
            return (
                {"display": "block"},
                {"display": "none"},
                {"display": "none"},
                {"display": "flex", "alignItems": "center"},
                {"display": "block"},
            )
        if tab == "session-analysis-tab":
            return (
                {"display": "none"},
                {"display": "block"},
                {"display": "none"},
                {"display": "flex", "alignItems": "center"},
                {"display": "block"},
            )
        return (
            {"display": "none"},
            {"display": "none"},
            {"display": "block"},
            {"display": "none"},
            {"display": "none"},
        )

    @app.callback(
        Output("live-drivers-dd", "options"),
        Output("live-drivers-dd", "value"),
        Input("live-refresh", "n_intervals"),
        Input("view-tabs", "value"),
        State("live-drivers-dd", "value"),
        prevent_initial_call=True,
    )
    def update_live_driver_filter(_, active_tab, current_values):
        if active_tab != "live-session-tab":
            raise PreventUpdate

        telemetry_provider.start_live_stream()
        snapshot = telemetry_provider.get_live_snapshot(include_archive_fallback=True)
        labels = snapshot.get("driver_labels", [])
        options = [{"label": "All Drivers", "value": "__ALL__"}] + [
            {"label": label, "value": label} for label in labels
        ]
        allowed = {opt["value"] for opt in options}
        current_values = current_values or []
        next_values = [value for value in current_values if value in allowed]
        if "__ALL__" in next_values:
            next_values = ["__ALL__"]
        return options, next_values

    @app.callback(
        Output("live-position-graph", "figure"),
        Output("live-gap-graph", "figure"),
        Output("live-pace-graph", "figure"),
        Output("live-session-status", "children"),
        Output("live-session-meta", "children"),
        Output("live-session-profile-note", "children"),
        Output("live-source-badge", "children"),
        Output("live-source-badge", "className"),
        Output("live-card-1-kicker", "children"),
        Output("live-card-1-title", "children"),
        Output("live-card-1-subtitle", "children"),
        Output("live-card-2-kicker", "children"),
        Output("live-card-2-title", "children"),
        Output("live-card-2-subtitle", "children"),
        Output("live-card-3-kicker", "children"),
        Output("live-card-3-title", "children"),
        Output("live-card-3-subtitle", "children"),
        Input("live-refresh", "n_intervals"),
        Input("view-tabs", "value"),
        Input("live-drivers-dd", "value"),
        prevent_initial_call=True,
    )
    def update_live_session_graphs(_, active_tab, selected_live_drivers):
        if active_tab != "live-session-tab":
            raise PreventUpdate

        telemetry_provider.start_live_stream()
        snapshot = telemetry_provider.get_live_snapshot(include_archive_fallback=True)

        position_df = snapshot["position_df"].copy()
        pit_lap_df = snapshot["pit_lap_df"].copy()
        gap_df = snapshot["gap_df"].copy()
        pace_df = snapshot["pace_df"].copy()
        bestlap_df = snapshot["bestlap_df"].copy()
        speed_df = snapshot["speed_df"].copy()
        stint_summary_df = snapshot["stint_summary_df"].copy()
        bestlap_summary_df = snapshot["bestlap_summary_df"].copy()

        selected_live_drivers = selected_live_drivers or []
        selected_set = {str(value) for value in selected_live_drivers}
        all_selected = "__ALL__" in selected_set

        if selected_live_drivers and not all_selected:
            selected_set = {str(value) for value in selected_live_drivers}
            position_df = position_df[position_df["driver_label"].isin(selected_set)]
            pit_lap_df = pit_lap_df[pit_lap_df["driver_label"].isin(selected_set)]
            gap_df = gap_df[gap_df["driver_label"].isin(selected_set)]
            pace_df = pace_df[pace_df["driver_label"].isin(selected_set)]
            bestlap_df = bestlap_df[bestlap_df["driver_label"].isin(selected_set)]
            speed_df = speed_df[speed_df["driver_label"].isin(selected_set)]
            stint_summary_df = stint_summary_df[stint_summary_df["driver_label"].isin(selected_set)]
            bestlap_summary_df = bestlap_summary_df[bestlap_summary_df["driver_label"].isin(selected_set)]

        fastest_lap_row = snapshot["fastest_lap_row"]
        if fastest_lap_row and selected_live_drivers and not all_selected:
            if str(fastest_lap_row.get("driver_label")) not in {
                str(value) for value in selected_live_drivers
            }:
                fastest_lap_row = None

        position_fig, gap_fig, pace_fig, profile = build_session_specific_live_figures(
            session_category=snapshot.get("session_category", "practice"),
            position_df=position_df,
            pit_lap_df=pit_lap_df,
            safety_laps=snapshot["safety_laps"],
            gap_df=gap_df,
            pace_df=pace_df,
            bestlap_df=bestlap_df,
            speed_df=speed_df,
            stint_summary_df=stint_summary_df,
            bestlap_summary_df=bestlap_summary_df,
            fastest_lap_row=fastest_lap_row,
        )

        status = snapshot["status"]
        filtered_driver_count = int(bestlap_summary_df["driver_label"].nunique()) if not bestlap_summary_df.empty else 0
        status_items = [
            html.Span(
                f"Stream Running: {'yes' if status['running'] else 'no'}",
                className="lap-context-item",
            ),
            html.Span(
                f"Buffered Events: {status['event_count']}",
                className="lap-context-item",
            ),
            html.Span(
                f"Drivers Tracked: {filtered_driver_count}/{snapshot['driver_count']}",
                className="lap-context-item",
            ),
            html.Span(
                f"Last Packet: {status.get('last_event_at') or '-'}",
                className="lap-context-item",
            ),
            html.Span(
                f"Safety Laps Marked: {len(snapshot['safety_laps'])}",
                className="lap-context-item",
            ),
            html.Span(
                f"Session Profile: {snapshot.get('session_category', 'practice').title()}",
                className="lap-context-item",
            ),
            html.Span(
                f"Data Source: {status.get('source', snapshot.get('source', 'live_stream'))}",
                className="lap-context-item",
            ),
        ]

        if status.get("last_error"):
            status_items.append(
                html.Span(
                    f"LiveF1 Error: {status['last_error']}",
                    className="lap-context-item lap-context-item--accent",
                )
            )
        if status.get("archive_error"):
            status_items.append(
                html.Span(
                    f"Archive Error: {status['archive_error']}",
                    className="lap-context-item lap-context-item--accent",
                )
            )

        session_meta = snapshot.get("session_meta", {})
        meta_items = [
            html.Span(
                f"Meeting: {session_meta.get('meeting_name', '-')}",
                className="lap-context-item",
            ),
            html.Span(
                f"Session: {session_meta.get('session_name', '-')}",
                className="lap-context-item",
            ),
            html.Span(
                f"Circuit: {session_meta.get('circuit_name', '-')} ({session_meta.get('country_name', '-')})",
                className="lap-context-item",
            ),
            html.Span(
                f"Session Status: {session_meta.get('session_status', '-')}",
                className="lap-context-item",
            ),
            html.Span(
                f"Track Status: {session_meta.get('track_status', '-')} - {session_meta.get('track_message', '-')}",
                className="lap-context-item",
            ),
        ]
        if status.get("archive_session_path"):
            meta_items.append(
                html.Span(
                    f"Archive Path: {status['archive_session_path']}",
                    className="lap-context-item",
                )
            )

        source = str(status.get("source", snapshot.get("source", "live_stream")))
        if source == "livef1_archive":
            badge_text = "ARCHIVE (LAST COMPLETED SESSION)"
            badge_class = "source-badge source-badge--archive"
        else:
            badge_text = "LIVE STREAM"
            badge_class = "source-badge source-badge--live"

        cards = profile.get("cards", [])
        card_defaults = [
            {"kicker": "Live", "title": "Graph 1", "subtitle": ""},
            {"kicker": "Live", "title": "Graph 2", "subtitle": ""},
            {"kicker": "Live", "title": "Graph 3", "subtitle": ""},
        ]
        cards = (cards + card_defaults)[:3]

        return (
            position_fig,
            gap_fig,
            pace_fig,
            status_items,
            meta_items,
            profile.get("profile_note", ""),
            badge_text,
            badge_class,
            cards[0]["kicker"],
            cards[0]["title"],
            cards[0]["subtitle"],
            cards[1]["kicker"],
            cards[1]["title"],
            cards[1]["subtitle"],
            cards[2]["kicker"],
            cards[2]["title"],
            cards[2]["subtitle"],
        )

    @app.callback(
        Output("lap-input", "max"),
        Output("lap-max-label", "children"),
        Input("year-dd", "value"),
        Input("gp-dd", "value"),
        Input("session-dd", "value"),
        Input("drivers-dd", "value"),
        Input("view-tabs", "value"),
        prevent_initial_call=True,
    )
    def update_lap_slider(year, gp, session_name, drivers, active_tab):
        if active_tab != "session-analysis-tab":
            raise PreventUpdate

        if year is None or gp is None or session_name is None or not drivers:
            raise PreventUpdate

        if not isinstance(drivers, list) or len(drivers) != 1:
            return 1, "/ 1 laps"

        driver = drivers[0]
        session = telemetry_provider.load_historical_session(year, int(gp), int(session_name))
        laps = prepare_session_laps(
            session=session,
            driver_code=driver,
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
        Input("drivers-dd", "value"),
        Input("view-tabs", "value"),
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
        drivers,
        active_tab,
    ):
        if active_tab != "session-analysis-tab":
            raise PreventUpdate

        max_lap = int(max_lap or 1)
        trigger_prop = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
        trigger = ctx.triggered_id

        current_value = int(input_value or 1)

        if trigger_prop in {
            "year-dd.value",
            "gp-dd.value",
            "session-dd.value",
            "drivers-dd.value",
            "view-tabs.value",
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
        Input("drivers-dd", "value"),
        Input("view-tabs", "value"),
        prevent_initial_call=True,
    )
    def update_full_session_graph(
        lap_number,
        year,
        gp,
        session_name,
        drivers,
        active_tab,
    ):
        if active_tab != "session-analysis-tab":
            raise PreventUpdate

        if (
            lap_number is None
            or year is None
            or gp is None
            or session_name is None
            or not drivers
        ):
            raise PreventUpdate

        if not isinstance(drivers, list) or len(drivers) != 1:
            return (
                _message_figure("Select exactly 1 driver for lap drilldown telemetry.", height=760),
                _message_figure("Select exactly 1 driver to compute lap delta to fastest.", height=360),
                [
                    html.Span(
                        "Lap drilldown supports one driver at a time.",
                        className="lap-context-item",
                    )
                ],
            )

        driver = drivers[0]
        session = telemetry_provider.load_historical_session(year, int(gp), int(session_name))
        laps = prepare_session_laps(
            session=session,
            driver_code=driver,
            valid_only=True,
        )

        if laps.empty:
            raise PreventUpdate

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
        )

        delta_fig = create_lap_delta_to_reference_figure(
            telemetry=selected_telemetry,
            reference_telemetry=fastest_telemetry,
            driver=driver,
            lap_number=selected_lap_number,
            reference_lap_number=fastest_lap_number,
        )

        selected_time_s = selected_lap["LapTime"].total_seconds()
        fastest_time_s = fastest_lap["LapTime"].total_seconds()
        delta_to_fastest = selected_time_s - fastest_time_s
        sign = "+" if delta_to_fastest >= 0 else "-"

        context = [
            html.Span(
                f"Selected Lap {selected_lap_number}: {format_td(selected_lap['LapTime'])}",
                className="lap-context-item",
            ),
            html.Span(
                f"Fastest Lap {fastest_lap_number}: {format_td(fastest_lap['LapTime'])}",
                className="lap-context-item",
            ),
            html.Span(
                f"Delta to fastest: {sign}{abs(delta_to_fastest):.3f}s",
                className="lap-context-item lap-context-item--accent",
            ),
        ]

        return full_session_fig, delta_fig, context

    @app.callback(
        Output("lap-time-evolution-graph", "figure"),
        Input("year-dd", "value"),
        Input("gp-dd", "value"),
        Input("session-dd", "value"),
        Input("drivers-dd", "value"),
        Input("view-tabs", "value"),
        prevent_initial_call=True,
    )
    def update_lap_time_evolution(year, gp, session_name, drivers, active_tab):
        if active_tab != "session-analysis-tab":
            raise PreventUpdate

        if year is None or gp is None or session_name is None or not drivers:
            raise PreventUpdate

        if not isinstance(drivers, list):
            raise PreventUpdate

        if len(drivers) > 2:
            return _message_figure("Select up to 2 drivers for lap-time evolution comparison.", height=430)

        session = telemetry_provider.load_historical_session(year, int(gp), int(session_name))
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
            raise PreventUpdate

        return create_lap_time_evolution_figure(payloads, session)
