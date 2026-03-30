import fastf1 
import os
from fastf1 import Cache
import pandas as pd
from numbers import Integral
from threading import RLock

CACHE_DIR = 'cache'

os.makedirs(CACHE_DIR, exist_ok=True)

#enable cache
Cache.enable_cache(CACHE_DIR)

SUPPORTED_EVENT_FORMATS = {
    "conventional",
    "sprint",
    "sprint_shootout",
    "sprint_qualifying",
    "testing",
}

_SESSION_CACHE = {}
_SESSION_CACHE_LOCK = RLock()


def get_supported_event_schedule(year: int):
    schedule = fastf1.get_event_schedule(year, include_testing=True)
    schedule = schedule[schedule["EventFormat"].isin(SUPPORTED_EVENT_FORMATS)]
    return schedule.reset_index(drop=True)


def _resolve_event_from_index(year: int, event_index: int):
    schedule = get_supported_event_schedule(year)
    if event_index < 0 or event_index >= len(schedule):
        raise ValueError(f"Invalid event index: {event_index}")
    return schedule, schedule.iloc[event_index]


def _normalize_session_key(year: int, gp, session_type):
    gp_key = int(gp) if isinstance(gp, Integral) else str(gp)
    session_key = int(session_type) if isinstance(session_type, Integral) else str(session_type)
    return int(year), gp_key, session_key


def _build_session(year: int, gp, session_type):
    if isinstance(gp, Integral):
        event_index = int(gp)
        schedule, event = _resolve_event_from_index(year, event_index)
        session_number = int(session_type)

        if event["EventFormat"] == "testing":
            # FastF1 testing sessions require test_number + session_number.
            test_number = int(
                (schedule.iloc[: event_index + 1]["EventFormat"] == "testing").sum()
            )
            return fastf1.get_testing_session(year, test_number, session_number)

        round_number = int(event["RoundNumber"])
        return fastf1.get_session(year, round_number, session_number)

    return fastf1.get_session(year, gp, session_type)


#session loader
def load_session(year: int, gp, session_type, telemetry=True):
    """
    Load and cache an F1 session
    
    :param year: Year of the session
    :type year: int
    :param gp: Event name (legacy) or supported event index
    :param session_type: Session identifier by name/code (legacy) or session number
    """

    key = _normalize_session_key(year, gp, session_type)

    with _SESSION_CACHE_LOCK:
        cached = _SESSION_CACHE.get(key)
        if cached is not None:
            has_telemetry = bool(getattr(cached, "_f1d_has_telemetry", False))
            if not telemetry or has_telemetry:
                return cached

    session = _build_session(year, gp, session_type)
    session.load(telemetry=telemetry, weather=False)
    setattr(session, "_f1d_has_telemetry", bool(telemetry))

    with _SESSION_CACHE_LOCK:
        existing = _SESSION_CACHE.get(key)
        if existing is not None:
            existing_has_telemetry = bool(getattr(existing, "_f1d_has_telemetry", False))
            if existing_has_telemetry or not telemetry:
                return existing

        _SESSION_CACHE[key] = session
        return session

#Telemetry extraction
def get_driver_telemetry(session, driver: str):
    """
    Returns Telemetry data for the selected driver's fastest lap
    
    :param session: Session Object
    :param driver: Driver abbr
    :type driver: str
    """

    lap = session.laps.pick_driver(driver).pick_fastest()
    if lap is None or lap.empty:
        return pd.DataFrame(columns=["Distance", "Speed", "Throttle", "Brake", "nGear", "X", "Y"])
    tel1 = lap.get_telemetry()

    tel = tel1.add_distance()

    return tel1[[
        "Distance", "Speed", "Throttle",
        "Brake", "nGear", "X", "Y"
    ]]


#fastest lap comparison
def fastest_lap_table(session, drivers):
    """
    Returns a dataframe of fastest lap times for the given list of drivers
    
    :param session: Session Object
    :param drivers: Driver number or abbr as list
    """

    rows = []

    for drv in drivers:
        lap = session.laps.pick_driver(drv).pick_fastest()
        if lap is None or lap.empty:
            continue

        rows.append({
            "Driver": drv,
            "LapTime": format_timedelta(lap["LapTime"]),
            "Sector1": format_timedelta(lap["Sector1Time"]),
            "Sector2": format_timedelta(lap["Sector2Time"]),
            "Sector3": format_timedelta(lap["Sector3Time"]),
        })

    return pd.DataFrame(rows)

#track map data
def get_track_coords(session, driver):
    """
    Fetch track coordinates info for a driver
    
    :param session: Session Object
    :param driver: Driver number or abbr
    """
    lap = session.laps.pick_driver(driver).pick_fastest()
    if lap is None or lap.empty:
        return pd.DataFrame(columns=["X", "Y"])
    tel1 = lap.get_telemetry()
    return tel1[['X', 'Y']]

#re-format time data
def format_timedelta(td):
    """
    Helper function for formatting time data
    
    :param td: Time data
    """
    if pd.isna(td):
        return "-"
    total_seconds = td.total_seconds()
    mins = int(total_seconds // 60)
    secs = total_seconds % 60
    return f"{mins}:{secs:06.3f}"
