import pandas as pd


def _session_part_label(value):
    if pd.isna(value):
        return "-"

    raw = str(value).strip()
    if not raw:
        return "-"

    upper = raw.upper()
    known = {
        "Q1", "Q2", "Q3",
        "SQ1", "SQ2", "SQ3",
    }
    alias_map = {"S1": "SQ1", "S2": "SQ2", "S3": "SQ3"}
    if upper in alias_map:
        return alias_map[upper]
    if upper in known:
        return upper

    try:
        num = int(float(raw))
        numeric_map = {
            0: "Q1",
            1: "Q2",
            2: "Q3",
            3: "Q3",
        }
        return numeric_map.get(num, raw)
    except Exception:
        return raw


def prepare_session_laps(session, driver_code, segment="ALL", valid_only=True, longest_stint=False):
    """
    Master function to prepare laps based on filters.
    """

    laps = get_driver_laps(session, driver_code)

    if valid_only:
        laps = filter_valid_laps(laps)

    laps = filter_session_segment(laps, segment)

    if longest_stint:
        laps = get_longest_stint(laps)

    return laps


def get_driver_laps(session, driver_code):
    """
    Returns all laps data for a specific driver in a session
    """

    laps = session.laps.pick_driver(driver_code)
    return laps

def filter_valid_laps(laps_df):
    """
    Filters out in-laps, out_laps, deleted laps and NaNs
    """
    valid_laps = laps_df[
        (laps_df['LapTime'].notna()) &
        (laps_df['PitInTime'].isna()) &
        (laps_df['PitOutTime'].isna()) 
    ]

    # Remove deleted laps
    if 'Deleted' in valid_laps.columns:
        valid_laps = valid_laps[valid_laps['Deleted'] == False]

    return valid_laps

def filter_session_segment(laps_df, segment):
    """
    Filter laps by Q1/Q2/Q3 if applicable
    segment: 'ALL', 'Q1', 'Q2', 'Q3'
    """

    if str(segment).upper() == "ALL":
        return laps_df
    
    if 'SessionPart' not in laps_df.columns:
        return laps_df.iloc[0:0]

    target = str(segment).upper()
    labeled = laps_df.copy()
    labeled["_SessionPartLabel"] = labeled["SessionPart"].apply(_session_part_label)
    filtered = labeled[labeled["_SessionPartLabel"] == target]
    return filtered.drop(columns=["_SessionPartLabel"])

def get_longest_stint(laps_df):
    """
    Returns laps belonging to the longest stint.
    """
    if 'Stint' not in laps_df.columns:
        return laps_df

    stint_counts = laps_df.groupby('Stint').size()
    longest_stint_number = stint_counts.idxmax()

    return laps_df[laps_df['Stint'] == longest_stint_number]

def get_lap_telemetry(lap):
    """
    Returns telemetry for a lap with distance added.
    """
    telemetry = lap.get_telemetry().add_distance()
    return telemetry

def safe_lap_selection(laps_df, lap_number):
    """
    Returns lap safely without crashing.
    """
    if lap_number not in laps_df['LapNumber'].values:
        return laps_df.iloc[0]

    return laps_df[laps_df['LapNumber'] == lap_number].iloc[0]

def get_lap_time_evolution_data(laps_df):
    """
    Returns processed dataframe for lap time evolution graph.
    """

    df = laps_df.copy()

    # convert lap time to seconds
    df['LapTimeSeconds'] = df['LapTime'].dt.total_seconds()

    # format lap times in mm:ss.SSS
    df['LapTimeFormatted'] = df['LapTime'].apply(
        lambda x: f"{int(x.total_seconds()//60)}:"
                  f"{int(x.total_seconds()%60):02d}."
                  f"{int(x.microseconds/1000):03d}"
        if pd.notna(x) else None
    )

    # Add the valid flag
    is_valid = (
        df['LapTime'].notna() &
        df['PitInTime'].isna() &
        df['PitOutTime'].isna()
    )
    if "Deleted" in df.columns:
        is_valid = is_valid & (df["Deleted"] != True)
    if "IsAccurate" in df.columns:
        is_valid = is_valid & (df["IsAccurate"] == True)
    df['IsValid'] = is_valid

    if "SessionPart" in df.columns:
        df["SessionPartLabel"] = df["SessionPart"].apply(_session_part_label)
    else:
        df["SessionPartLabel"] = "-"

    # Fastest lap index
    fastest_idx = df['LapTimeSeconds'].idxmin()

    return df, fastest_idx
