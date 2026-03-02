import pandas as pd

from services.telemetry_service import get_fastest_laps


def normalize_selected_drivers(drivers):
    if not drivers:
        return []
    if isinstance(drivers, list):
        return drivers
    return [drivers]


def resolve_fastest_laps(session, drivers):
    selected_drivers = normalize_selected_drivers(drivers)
    official_fastest_laps = get_fastest_laps(session, selected_drivers)
    fallback_drivers = []

    if len(official_fastest_laps) < len(selected_drivers):
        fallback_fastest_laps = get_fastest_laps(
            session,
            selected_drivers,
            only_by_time=True,
        )
        for drv in selected_drivers:
            if drv not in official_fastest_laps and drv in fallback_fastest_laps:
                official_fastest_laps[drv] = fallback_fastest_laps[drv]
                fallback_drivers.append(drv)

    return official_fastest_laps, fallback_drivers, selected_drivers


def build_fastest_lap_table(fastest_laps, selected_drivers):
    columns = []
    data = []

    if not fastest_laps:
        return columns, data

    columns = [
        {"name": "Driver", "id": "Driver"},
        {"name": "LapTime", "id": "LapTime"},
        {"name": "Sector1", "id": "Sector1"},
        {"name": "Sector2", "id": "Sector2"},
        {"name": "Sector3", "id": "Sector3"},
    ]
    data = [
        {
            "Driver": drv,
            "LapTime": format_td(lap["LapTime"]),
            "Sector1": format_td(lap["Sector1Time"]),
            "Sector2": format_td(lap["Sector2Time"]),
            "Sector3": format_td(lap["Sector3Time"]),
        }
        for drv in selected_drivers
        if drv in fastest_laps
        for lap in [fastest_laps[drv]]
    ]
    return columns, data


def build_fastest_lap_note(session, selected_drivers, fallback_drivers):
    if not fallback_drivers:
        return ""

    fallback_labels = ", ".join(str(drv) for drv in fallback_drivers)
    note_parts = [
        f"Official fastest laps were unavailable for {fallback_labels}.",
        "Showing unofficial quickest laps by recorded time.",
    ]

    selected_laps = session.laps.pick_drivers(selected_drivers)
    if "IsPersonalBest" in selected_laps.columns:
        selected_pb = int((selected_laps["IsPersonalBest"] == True).sum())
        if selected_pb == 0:
            note_parts.append(
                "No selected-driver laps are marked as personal best by the timing feed."
            )
    if "IsAccurate" in selected_laps.columns:
        selected_accurate = int((selected_laps["IsAccurate"] == True).sum())
        if selected_accurate == 0:
            note_parts.append(
                "All selected-driver laps are marked non-accurate for this session."
            )

    return " ".join(note_parts)


def format_td(td):
    if pd.isna(td):
        return "--"
    total_seconds = td.total_seconds()
    mins = int(total_seconds // 60)
    secs = total_seconds % 60
    return f"{mins}:{secs:06.3f}"
