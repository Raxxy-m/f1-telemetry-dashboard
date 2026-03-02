import pandas as pd


def compute_comparison_kpi_rows(session, fastest_laps, driver_tel):
    if len(fastest_laps) != 2:
        return _empty_kpi_rows()

    driver_1, driver_2 = list(fastest_laps.keys())
    if driver_1 not in driver_tel or driver_2 not in driver_tel:
        return _empty_kpi_rows()

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
        {
            "title": "Fastest Lap Gap",
            "value": f"{lap_gap:.3f}s",
            "detail": f"{faster_abbr} ahead on fastest lap",
        },
        {
            "title": "Top Speed Delta",
            "value": f"{top_adv:.1f} km/h",
            "detail": top_detail,
        },
        {
            "title": "Average Speed Delta",
            "value": f"{avg_adv:.2f} km/h",
            "detail": avg_detail,
        },
        {
            "title": "Largest Sector Swing",
            "value": f"S{max_sector_idx + 1} {abs(swing_val):.3f}s",
            "detail": f"{swing_winner} strongest sector edge",
        },
    ]


def _empty_kpi_rows():
    return [
        {
            "title": "Fastest Lap Gap",
            "value": "--",
            "detail": "Select exactly 2 drivers to unlock comparison KPIs.",
        },
        {
            "title": "Top Speed Delta",
            "value": "--",
            "detail": "Comparison unavailable.",
        },
        {
            "title": "Average Speed Delta",
            "value": "--",
            "detail": "Comparison unavailable.",
        },
        {
            "title": "Largest Sector Swing",
            "value": "--",
            "detail": "Comparison unavailable.",
        },
    ]


def _safe_td_seconds(td):
    return td.total_seconds() if pd.notna(td) else 0.0
