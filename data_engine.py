import fastf1 
import os
from fastf1 import Cache
import pandas as pd

CACHE_DIR = 'cache'

os.makedirs(CACHE_DIR, exist_ok=True)

#enable cache
Cache.enable_cache(CACHE_DIR)

#session loader
def load_session(year: int, gp: str, session_type: str):
    """
    Load and cache an F1 session
    
    :param year: Year of the session
    :type year: int
    :param gp: Name of the Grand Prix/Round Number
    :type gp: str
    :param session_type: Session Type(Practice, Race etc.)
    :type session_type: str
    """

    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=True, weather=False)
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
        if lap.empty:
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

