# callbacks.py

from dash import Input, Output, State, html
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
import traceback
import pandas as pd

from services.telemetry_service import get_fastest_laps, prepare_telemetry, compute_binary_delta
from services.style_service import extract_driver_styles
from figures.telemetry_figure import build_telemetry_figure
from figures.track_figure import build_single_driver_track, build_binary_delta_track, build_multi_driver_message
from figures.mini_track_figure import build_mini_track


from fastf1 import get_event_schedule, get_event

from data_engine import (
    load_session,
    fastest_lap_table,
)

def register_callbacks(app):

    # ==========================================================
    # Populate Grand Prix Dropdown
    # ==========================================================
    @app.callback(
        Output("gp-dd", "options"),
        Input("year-dd", "value")
    )
    def update_gp_dropdown(year):
        if not year:
            return []

        schedule = get_event_schedule(year)

        return [
            {"label": row["EventName"], "value": row["EventName"]}
            for _, row in schedule.iterrows()
        ]


    # ==========================================================
    # Populate Session Dropdown (Sprint-safe)
    # ==========================================================
    @app.callback(
        Output("session-dd", "options"),
        Input("year-dd", "value"),
        Input("gp-dd", "value")
    )
    def update_sessions(year, gp):
        if not all([year, gp]):
            return []

        event = get_event(year, gp)

        # Only pick SessionX columns (not SessionXDate)
        session_columns = [
            col for col in event.index
            if col.startswith("Session") and "Date" not in col
        ]

        options = []

        for col in session_columns:
            session_name = event[col]

            if pd.isna(session_name):
                continue

            # Map readable name → FastF1 session code
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

            # Match dynamically
            for key in mapping:
                if key in session_name:
                    options.append({
                        "label": session_name,
                        "value": mapping[key]
                    })
                    break

        return options


    # ==========================================================
    # Populate Driver Dropdown
    # ==========================================================
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
                "value": d
            }
            for d in session.drivers
        ]


    # ==========================================================
    # Main Dashboard Update
    # ==========================================================
    @app.callback(
        Output("telemetry-graph", "figure"),
        Output("track-delta", "figure"),
        Output("fastest-lap-table", "data"),
        Output("fastest-lap-table", "columns"),
        Output("debug-output", "children"),
        Output("telemetry-store", "data"),
        Input("year-dd", "value"),
        Input("gp-dd", "value"),
        Input("session-dd", "value"),
        Input("drivers-dd", "value")
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

            if not all([year, gp, session_type, drivers]):
                return go.Figure(), go.Figure(), [], [], "\n".join(debug_lines), {}

            session = load_session(year, gp, session_type)

            debug_lines.append("Session loaded successfully")
            debug_lines.append(f"Event: {session.event['EventName']}")
            debug_lines.append(f"Total laps: {len(session.laps)}")
            debug_lines.append("")

            # ==================================================
            # TELEMETRY + MINI MAP
            # ==================================================
            fastest_laps = get_fastest_laps(session, drivers)
            

            driver_tel = {}

            for drv, lap in fastest_laps.items():
                tel = prepare_telemetry(lap)
                driver_tel[drv] = tel
                debug_lines.append(
                    f"{drv}: Telemetry rows = {len(tel)}"
                )

            driver_style = extract_driver_styles(session, drivers)

            store_payload = {
                "telemetry": {
                    drv: tel.to_dict("records")
                    for drv, tel in driver_tel.items()
                },
                "styles": driver_style
            }

            
            telemetry_fig = build_telemetry_figure(driver_tel, session)
            
            # hover_distance = None
            # if hoverData and "points" in hoverData:
            #     hover_distance = hoverData['points'][0]['x']

            # mini_fig = build_mini_track(session, driver_tel, hover_distance)

            debug_lines.append(f"Drivers plotted: {len(driver_tel)}")
            debug_lines.append("")           

            # ==================================================
            # TRACK DELTA (Tempish)
            # ==================================================
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
                    lap2_time
                )

                track_fig = build_binary_delta_track(
                    delta_tel,
                    drv1,
                    drv2,
                    faster_index,
                    session
                )

            else:

                track_fig = build_multi_driver_message()

            # ==================================================
            # FASTEST LAP TABLE
            # ==================================================
            columns = []
            data = {}

            df = fastest_lap_table(session, drivers)
            
            if df.empty:
                debug_lines.append("Fastest lap table empty")
            else:
                columns = [
                    {"name": col, "id": col}
                    for col in df.columns
                ]

                data = df.to_dict("records")
                debug_lines.append("Fastest lap table populated")

            return (
                telemetry_fig,
                track_fig,
                data,
                columns,
                "\n".join(debug_lines),
                store_payload
            )

        except Exception:
            return (
                go.Figure(),
                go.Figure(),
                [],
                [],
                "ERROR:\n" + traceback.format_exc(),
                {}
            )
        
    # ==========================================================
    # Mini Map Update
    # ==========================================================
        
    @app.callback(
        Output("mini-track-map", "figure"),
        Input("telemetry-graph", "hoverData"),
        State("telemetry-store", "data"),
    )
    def update_mini_map(hoverData, stored_data):
        if not stored_data:
            return go.Figure()

        telemetry_data = stored_data["telemetry"]
        driver_styles = stored_data["styles"]

        # Convert back to DataFrames
        driver_tel = {
            drv: pd.DataFrame(data)
            for drv, data in telemetry_data.items()
        }

        reference_distance = None
        if hoverData and "points" in hoverData:
            reference_distance = hoverData["points"][0]["x"]

        return build_mini_track(
            driver_tel=driver_tel,
            driver_styles=driver_styles,
            reference_distance=reference_distance
        )
