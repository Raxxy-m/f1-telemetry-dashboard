import os

import numpy as np
import pandas as pd


TELEMETRY_COLUMNS = [
    "Distance",
    "Time",
    "Speed",
    "Throttle",
    "Brake",
    "RPM",
    "nGear",
    "X",
    "Y",
]


def _env_positive_int(name, default):
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


MAX_OVERLAY_POINTS = _env_positive_int("F1D_OVERLAY_POINTS", 1200)


def _normalize_brake(series):
    brake = pd.to_numeric(series, errors="coerce")
    finite = brake[np.isfinite(brake)]
    if not finite.empty and float(finite.max()) <= 1.5:
        brake = brake * 100.0
    return brake.clip(lower=0.0, upper=100.0)


def _downsample_telemetry(telemetry, max_points):
    if max_points is None or max_points <= 0 or len(telemetry) <= max_points:
        return telemetry
    if "Distance" not in telemetry.columns:
        return telemetry

    sampled = telemetry.dropna(subset=["Distance"]).sort_values("Distance", kind="mergesort")
    sampled = sampled[~sampled["Distance"].duplicated(keep="first")]
    if len(sampled) <= max_points:
        return sampled.reset_index(drop=True)

    sample_idx = np.linspace(0, len(sampled) - 1, max_points, dtype=np.int64)
    return sampled.iloc[sample_idx].reset_index(drop=True)


def extract_lap_telemetry(lap, max_points=None):
    if lap is None or lap.empty:
        return pd.DataFrame(columns=TELEMETRY_COLUMNS)

    telemetry = lap.get_telemetry().add_distance()
    selected_columns = [col for col in TELEMETRY_COLUMNS if col in telemetry.columns]
    telemetry = telemetry.loc[:, selected_columns].copy()

    if "Brake" in telemetry.columns:
        telemetry["Brake"] = _normalize_brake(telemetry["Brake"])

    for column in ("Distance", "Speed", "Throttle", "Brake", "RPM", "nGear", "X", "Y"):
        if column in telemetry.columns:
            telemetry[column] = pd.to_numeric(telemetry[column], errors="coerce").astype("float32")

    telemetry = _downsample_telemetry(telemetry, max_points=max_points)
    return telemetry

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

    return extract_lap_telemetry(lap, max_points=MAX_OVERLAY_POINTS)

def compute_binary_delta(lap1_tel, lap2_tel, lap1_time, lap2_time):
    """
    Computes time delta between two telemetry laps by auto selecting faster lap as reference
    """

    if lap1_time <= lap2_time:
        ref_tel = lap1_tel
        cmp_tel = lap2_tel
        faster_index = 0
    else:
        ref_tel = lap2_tel
        cmp_tel = lap1_tel
        faster_index = 1

    if ref_tel.empty or cmp_tel.empty:
        return pd.DataFrame(columns=["Distance", "X", "Y", "Delta"]), faster_index

    ref_distance = pd.to_numeric(ref_tel["Distance"], errors="coerce").to_numpy(dtype=float, copy=False)
    cmp_distance = pd.to_numeric(cmp_tel["Distance"], errors="coerce").to_numpy(dtype=float, copy=False)
    ref_seconds = ref_tel["Time"].dt.total_seconds().to_numpy(dtype=float, copy=False)
    cmp_seconds = cmp_tel["Time"].dt.total_seconds().to_numpy(dtype=float, copy=False)

    ref_valid = np.isfinite(ref_distance) & np.isfinite(ref_seconds)
    cmp_valid = np.isfinite(cmp_distance) & np.isfinite(cmp_seconds)

    if ref_valid.sum() < 2 or cmp_valid.sum() < 2:
        output = ref_tel.loc[:, [col for col in ("Distance", "X", "Y") if col in ref_tel.columns]].copy()
        output["Delta"] = np.nan
        return output, faster_index

    cmp_order = np.argsort(cmp_distance[cmp_valid])
    cmp_sorted_distance = cmp_distance[cmp_valid][cmp_order]
    cmp_sorted_seconds = cmp_seconds[cmp_valid][cmp_order]

    delta = np.full(ref_distance.shape, np.nan, dtype=float)
    interpolated = np.interp(ref_distance[ref_valid], cmp_sorted_distance, cmp_sorted_seconds)
    delta[ref_valid] = interpolated - ref_seconds[ref_valid]
    smoothed_delta = pd.Series(delta).rolling(7, center=True, min_periods=1).mean().to_numpy(dtype=float)

    output = ref_tel.loc[:, [col for col in ("Distance", "X", "Y") if col in ref_tel.columns]].copy()
    output["Delta"] = smoothed_delta.astype("float32")
    return output, faster_index
