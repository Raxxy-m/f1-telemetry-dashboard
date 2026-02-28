from dash import Input, Output, State, html
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go
import traceback
import pandas as pd

from services.telemetry_service import (
    get_fastest_laps,
    prepare_telemetry,
    compute_binary_delta,
)
from services.style_service import extract_driver_styles
from services.session_telemetry_services import (
    prepare_session_laps,
    safe_lap_selection,
    get_lap_telemetry,
    get_lap_time_evolution_data,
)
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

from fastf1 import get_event_schedule, get_event

from data_engine import load_session, fastest_lap_table


def _blank_fig():
    return go.Figure()


def _format_td(td):
    if pd.isna(td):
        return "--"
    total_seconds = td.total_seconds()
    mins = int(total_seconds // 60)
    secs = total_seconds % 60
    return f"{mins}:{secs:06.3f}"


def _safe_td_seconds(td):
    return td.total_seconds() if pd.notna(td) else 0.0


def _metric_card(title, value, detail):
    return html.Div(
        [
            html.Div(title, className="metric-card-title"),
            html.Div(value, className="metric-card-value"),
            html.Div(detail, className="metric-card-detail"),
        ],
        className="metric-card",
    )


def _build_kpi_cards(session, fastest_laps, driver_tel):
    if len(fastest_laps) != 2:
        return [
            _metric_card(
                "Fastest Lap Gap",
                "--",
                "Select exactly 2 drivers to unlock comparison KPIs.",
            ),
            _metric_card("Top Speed Delta", "--", "Comparison unavailable."),
            _metric_card("Average Speed Delta", "--", "Comparison unavailable."),
            _metric_card("Largest Sector Swing", "--", "Comparison unavailable."),
        ]

    driver_1, driver_2 = list(fastest_laps.keys())
    lap_1 = fastest_laps[driver_1]
    lap_2 = fastest_laps[driver_2]

    abbr_1 = session.get_driver(driver_1)["Abbreviation"]
    abbr_2 = session.get_driver(driver_2)["Abbreviation"]

    lap_1_s = lap_1["LapTime"].total_seconds()
    lap_2_s = lap_2["LapTime"].total_seconds()

    if lap_1_s <= lap_2_s:
        faster_abbr = abbr_1
        lap_gap = lap_2_s - lap_1_s
    else:
        faster_abbr = abbr_2
        lap_gap = lap_1_s - lap_2_s

    tel_1 = driver_tel[driver_1]
    tel_2 = driver_tel[driver_2]

    top_1 = float(tel_1["Speed"].max())
    top_2 = float(tel_2["Speed"].max())
    avg_1 = float(tel_1["Speed"].mean())
    avg_2 = float(tel_2["Speed"].mean())

    if top_1 >= top_2:
        top_adv = top_1 - top_2
        top_detail = f"{abbr_1} higher vmax"
    else:
        top_adv = top_2 - top_1
        top_detail = f"{abbr_2} higher vmax"

    if avg_1 >= avg_2:
        avg_adv = avg_1 - avg_2
        avg_detail = f"{abbr_1} higher average"
    else:
        avg_adv = avg_2 - avg_1
        avg_detail = f"{abbr_2} higher average"

    sector_deltas = [
        _safe_td_seconds(lap_2["Sector1Time"]) - _safe_td_seconds(lap_1["Sector1Time"]),
        _safe_td_seconds(lap_2["Sector2Time"]) - _safe_td_seconds(lap_1["Sector2Time"]),
        _safe_td_seconds(lap_2["Sector3Time"]) - _safe_td_seconds(lap_1["Sector3Time"]),
    ]
    max_sector_idx = max(range(len(sector_deltas)), key=lambda idx: abs(sector_deltas[idx]))
    swing_val = sector_deltas[max_sector_idx]
    swing_winner = abbr_1 if swing_val >= 0 else abbr_2

    return [
        _metric_card(
            "Fastest Lap Gap",
            f"{lap_gap:.3f}s",
            f"{faster_abbr} ahead on fastest lap",
        ),
        _metric_card(
            "Top Speed Delta",
            f"{top_adv:.1f} km/h",
            top_detail,
        ),
        _metric_card(
            "Average Speed Delta",
            f"{avg_adv:.2f} km/h",
            avg_detail,
        ),
        _metric_card(
            "Largest Sector Swing",
            f"S{max_sector_idx + 1} {abs(swing_val):.3f}s",
            f"{swing_winner} strongest sector edge",
        ),
    ]


def register_callbacks(app):
    @app.callback(
        Output("gp-dd", "options"),
        Input("year-dd", "value"),
    )
    def update_gp_dropdown(year):
        if not year:
            return []

        schedule = get_event_schedule(year)
        return [
            {"label": row["EventName"], "value": row["EventName"]}
            for _, row in schedule.iterrows()
        ]

    @app.callback(
        Output("session-dd", "options"),
        Input("year-dd", "value"),
        Input("gp-dd", "value"),
    )
    def update_sessions(year, gp):
        if not all([year, gp]):
            return []

        event = get_event(year, gp)
        session_columns = [
            col for col in event.index
            if col.startswith("Session") and "Date" not in col
        ]

        options = []
        mapping = {
            "Practice 1": "FP1",
            "Practice 2": "FP2",
            "Practice 3": "FP3",
            "Sprint Qualifying": "SQ",
            "Sprint Shootout": "SS",
            "Sprint": "S",
            "Qualifying": "Q",
            "Race": "R",
        }

        for col in session_columns:
            session_name = event[col]
            if pd.isna(session_name):
                continue
            for key in mapping:
                if key in session_name:
                    options.append({"label": session_name, "value": mapping[key]})
                    break

        return options

    @app.callback(
        Output("drivers-dd", "options"),
        Input("year-dd", "value"),
        Input("gp-dd", "value"),
        Input("session-dd", "value"),
    )
    def update_drivers(year, gp, session_type):
        if not all([year, gp, session_type]):
            return []

        session = load_session(year, gp, session_type)
        return [
            {
                "label": f"{session.get_driver(d)['Abbreviation']} ({d})",
                "value": d,
            }
            for d in session.drivers
        ]

    @app.callback(
        Output("telemetry-graph", "figure"),
        Output("comparison-kpi-cards", "children"),
        Output("delta-graph", "figure"),
        Output("sector-delta-bars", "figure"),
        Output("speed-profile-graph", "figure"),
        Output("track-delta", "figure"),
        Output("fastest-lap-table", "data"),
        Output("fastest-lap-table", "columns"),
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

            if not all([year, gp, session_type, drivers]):
                return (
                    _blank_fig(),
                    _build_kpi_cards(None, {}, {}),
                    _blank_fig(),
                    _blank_fig(),
                    _blank_fig(),
                    _blank_fig(),
                    [],
                    [],
                    "\n".join(debug_lines),
                    {},
                )

            session = load_session(year, gp, session_type)

            debug_lines.append("Session loaded successfully")
            debug_lines.append(f"Event: {session.event['EventName']}")
            debug_lines.append(f"Total laps: {len(session.laps)}")
            debug_lines.append("")

            fastest_laps = get_fastest_laps(session, drivers)
            driver_tel = {}
            for drv, lap in fastest_laps.items():
                tel = prepare_telemetry(lap)
                driver_tel[drv] = tel
                debug_lines.append(f"{drv}: Telemetry rows = {len(tel)}")

            driver_style = extract_driver_styles(session, drivers)

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
            kpi_cards = _build_kpi_cards(session, fastest_laps, driver_tel)

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

            columns = []
            data = []
            df = fastest_lap_table(session, drivers)
            if df.empty:
                debug_lines.append("Fastest lap table empty")
            else:
                columns = [{"name": col, "id": col} for col in df.columns]
                data = df.to_dict("records")
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
                "\n".join(debug_lines),
                store_payload,
            )
        except Exception:
            return (
                _blank_fig(),
                _build_kpi_cards(None, {}, {}),
                _blank_fig(),
                _blank_fig(),
                _blank_fig(),
                _blank_fig(),
                [],
                [],
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
        Input("view-tabs", "value"),
    )
    def toggle_tabs(tab):
        if tab == "performance-comparison-tab":
            return {"display": "block"}, {"display": "none"}
        return {"display": "none"}, {"display": "block"}

    @app.callback(
        Output("lap-slider", "max"),
        Output("lap-slider", "value"),
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

        if not all([year, gp, session_name, drivers]):
            raise PreventUpdate

        if not isinstance(drivers, list) or len(drivers) != 1:
            raise PreventUpdate

        driver = drivers[0]
        session = load_session(year, gp, session_name)
        laps = prepare_session_laps(
            session=session,
            driver_code=driver,
            valid_only=True,
        )

        if laps.empty:
            return 1, 1

        max_lap = int(laps["LapNumber"].max())
        return max_lap, 1

    @app.callback(
        Output("full-session-telemetry-graph", "figure"),
        Output("lap-delta-fastest-graph", "figure"),
        Output("lap-context", "children"),
        Input("lap-slider", "value"),
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

        if not all([lap_number, year, gp, session_name, drivers]):
            raise PreventUpdate

        if not isinstance(drivers, list) or len(drivers) != 1:
            raise PreventUpdate

        driver = drivers[0]
        session = load_session(year, gp, session_name)
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
                f"Selected Lap {selected_lap_number}: {_format_td(selected_lap['LapTime'])}",
                className="lap-context-item",
            ),
            html.Span(
                f"Fastest Lap {fastest_lap_number}: {_format_td(fastest_lap['LapTime'])}",
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

        if not all([year, gp, session_name, drivers]):
            raise PreventUpdate

        if not isinstance(drivers, list) or len(drivers) != 1:
            raise PreventUpdate

        driver = drivers[0]
        session = load_session(year, gp, session_name)
        laps = session.laps.pick_drivers(driver)

        if laps.empty:
            raise PreventUpdate

        df, fastest_idx = get_lap_time_evolution_data(laps)
        return create_lap_time_evolution_figure(df, fastest_idx, driver, session)
