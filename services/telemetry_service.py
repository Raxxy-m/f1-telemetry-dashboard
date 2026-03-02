import pandas as pd
import numpy as np

def get_fastest_laps(session, drivers, only_by_time=False):
    """
    Return dict: {driver: fastest_lap}
    
    :param session: Session object
    :param drivers: Driver abbr or number(either list or individual)
    """
    result = {}

    if drivers is None:
        return result
    if not isinstance(drivers, (list, tuple, set, pd.Index, np.ndarray)):
        drivers = [drivers]

    for drv in drivers:
        drv_laps = session.laps.pick_drivers(drv)

        if drv_laps.empty:
            continue
        fastest = drv_laps.pick_fastest(only_by_time=only_by_time)

        # FastF1 can return None when there is no valid timed lap.
        if fastest is None or fastest.empty:
            continue
        result[drv] = fastest
    
    return result

def prepare_telemetry(lap):
    """
    Converts raw Telemetry into cleaned Telemetry Dataframe

    :param lap: Lap Data
    """

    tel = lap.get_telemetry().add_distance()

    # scale the brake value
    tel['Brake'] = tel['Brake'].astype(int) * 100

    return tel

def compute_binary_delta(lap1_tel, lap2_tel, lap1_time, lap2_time):
    """
    Computes time delta between two telemetry laps by auto selecting faster lap as reference
    """

    # Determine faster driver
    if lap1_time <= lap2_time:
        ref_tel = lap1_tel.copy()
        cmp_tel = lap2_tel.copy()
        faster_index = 0
    else:
        ref_tel = lap2_tel.copy()
        cmp_tel = lap1_tel.copy()
        faster_index = 1

    ref_time = ref_tel["Time"].dt.total_seconds()
    cmp_time = cmp_tel["Time"].dt.total_seconds()

    cmp_interp = np.interp(
        ref_tel["Distance"],
        cmp_tel["Distance"],
        cmp_time
    )

    delta = cmp_interp - ref_time

    ref_tel["Delta"] = delta.rolling(7, center=True).mean()

    return ref_tel, faster_index
