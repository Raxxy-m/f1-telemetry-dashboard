from __future__ import annotations

import itertools
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import pandas as pd

SAFE_LIVE_TOPICS: tuple[str, ...] = (
    "DriverList",
    "ExtrapolatedClock",
    "Heartbeat",
    "RaceControlMessages",
    "SessionInfo",
    "SessionStatus",
    "TimingData",
    "TimingStats",
    "TrackStatus",
    "WeatherData",
)

SAFE_ARCHIVE_TOPICS: tuple[str, ...] = (
    "DriverList",
    "SessionInfo",
    "SessionStatus",
    "TrackStatus",
    "TimingData",
    "TimingStats",
    "RaceControlMessages",
    "ExtrapolatedClock",
    "Heartbeat",
    "WeatherData",
)

ARCHIVE_STREAM_TOPICS: set[str] = {
    "TimingData",
    "TimingStats",
    "RaceControlMessages",
    "SessionStatus",
    "TrackStatus",
    "ExtrapolatedClock",
    "Heartbeat",
    "WeatherData",
}

ARCHIVE_CACHE_TTL_SECONDS = 300
LIVE_STALE_SECONDS = 90
SPRINT_WINDOW_SWITCH_LAP = 5

SAFETY_STATUS_CODES = {"4", "5", "6", "7"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _parse_duration_seconds(raw_value: Any) -> float | None:
    if raw_value is None:
        return None

    text = str(raw_value).strip()
    if not text or text in {"-", "nan", "None"}:
        return None

    sign = -1.0 if text.startswith("-") else 1.0
    text = text.lstrip("+-")
    if not text:
        return None

    parts = text.split(":")
    try:
        if len(parts) == 1:
            total = float(parts[0])
        elif len(parts) == 2:
            minutes = float(parts[0])
            seconds = float(parts[1])
            total = (minutes * 60.0) + seconds
        elif len(parts) == 3:
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            total = (hours * 3600.0) + (minutes * 60.0) + seconds
        else:
            return None
    except ValueError:
        return None

    return sign * total


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"-", "nan", "None"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_team_color(raw_value: Any) -> str | None:
    if raw_value is None:
        return None
    value = str(raw_value).strip()
    if not value:
        return None
    if value.startswith("#"):
        return value
    if len(value) in {6, 8}:
        return f"#{value}"
    return None


def _parse_utc_datetime(raw_value: Any) -> datetime | None:
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text or text in {"-", "None", "nan"}:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _session_end_utc(session_payload: dict[str, Any]) -> datetime | None:
    end_dt = _parse_utc_datetime(session_payload.get("EndDate"))
    if end_dt is not None:
        return end_dt
    return _parse_utc_datetime(session_payload.get("StartDate"))


def _select_last_completed_session(
    season_payload: dict[str, Any],
    now_utc: datetime,
) -> dict[str, Any] | None:
    meetings = season_payload.get("Meetings")
    if not isinstance(meetings, list):
        return None

    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for meeting in meetings:
        if not isinstance(meeting, dict):
            continue
        sessions = meeting.get("Sessions")
        if not isinstance(sessions, list):
            continue
        for session in sessions:
            if not isinstance(session, dict):
                continue
            session_path = session.get("Path")
            if not session_path:
                continue
            session_end = _session_end_utc(session)
            if session_end is None or session_end > now_utc:
                continue
            candidates.append((session_end, {"meeting": meeting, "session": session}))

    if not candidates:
        return None

    _, latest = max(candidates, key=lambda item: item[0])
    return latest


def _build_live_dataframes(events: list[dict[str, Any]]) -> dict[str, Any]:
    driver_lookup: dict[str, dict[str, Any]] = {}
    timing_rows: list[dict[str, Any]] = []
    safety_laps: set[int] = set()
    current_track_status: str | None = None
    current_track_message: str | None = None
    latest_session_info: dict[str, Any] | None = None
    latest_session_status: str | None = None

    for event in events:
        topic = event.get("topic")
        payload = event.get("payload")

        if topic == "DriverList" and isinstance(payload, dict):
            racing_number = str(payload.get("RacingNumber", "")).strip()
            if not racing_number:
                continue
            driver_lookup[racing_number] = {
                "driver_label": str(
                    payload.get("Tla")
                    or payload.get("BroadcastName")
                    or racing_number
                ).strip(),
                "team_name": payload.get("TeamName"),
                "team_color": _normalize_team_color(payload.get("TeamColour")),
            }
            continue

        if topic == "TrackStatus" and isinstance(payload, dict):
            status_value = payload.get("Status")
            if status_value is not None:
                current_track_status = str(status_value).strip()
            message_value = payload.get("Message")
            if message_value:
                current_track_message = str(message_value).strip()
            continue

        if topic == "SessionInfo" and isinstance(payload, dict):
            latest_session_info = payload
            continue

        if topic == "SessionStatus" and isinstance(payload, dict):
            latest_session_status = str(
                payload.get("status") or payload.get("Status") or ""
            ).strip() or latest_session_status
            continue

        if topic != "TimingData" or not isinstance(payload, dict):
            continue

        driver_no = str(
            payload.get("DriverNo")
            or payload.get("RacingNumber")
            or payload.get("Driver")
            or ""
        ).strip()
        lap_number = _safe_int(payload.get("NumberOfLaps"))
        position = _safe_int(payload.get("Position"))
        in_pit = bool(payload.get("InPit", False))

        if lap_number is not None and current_track_status in SAFETY_STATUS_CODES:
            safety_laps.add(lap_number)

        driver_info = driver_lookup.get(driver_no, {})
        driver_label = str(driver_info.get("driver_label") or driver_no or "Unknown")

        timing_rows.append(
            {
                "seq": _safe_int(event.get("seq")) or 0,
                "received_at": event.get("received_at"),
                "driver_no": driver_no,
                "driver_label": driver_label,
                "team_name": driver_info.get("team_name"),
                "team_color": driver_info.get("team_color"),
                "lap_number": lap_number,
                "position": position,
                "in_pit": in_pit,
                "gap_to_leader_s": _parse_duration_seconds(
                    payload.get("TimeDiffToFastest") or payload.get("GapToLeader")
                ),
                "gap_to_ahead_s": _parse_duration_seconds(
                    payload.get("TimeDiffToPositionAhead")
                ),
                "last_lap_time_s": _parse_duration_seconds(
                    payload.get("LastLapTime_Value")
                ),
                "best_lap_time_s": _parse_duration_seconds(
                    payload.get("BestLapTime_Value")
                ),
                "best_lap_lap": _safe_int(payload.get("BestLapTime_Lap")),
                "speed_trap_kph": _safe_float(payload.get("Speeds_ST_Value")),
                "number_of_pit_stops": _safe_int(payload.get("NumberOfPitStops")),
            }
        )

    session_meta = _build_session_meta(
        latest_session_info=latest_session_info,
        latest_session_status=latest_session_status,
        track_status=current_track_status,
        track_message=current_track_message,
    )
    session_category = _classify_session(session_meta)
    is_sprint_session = _is_sprint_session(session_meta)

    if not timing_rows:
        empty_df = pd.DataFrame()
        return {
            "timing_df": empty_df,
            "position_df": empty_df,
            "pit_lap_df": empty_df,
            "gap_df": empty_df,
            "pace_df": empty_df,
            "bestlap_df": empty_df,
            "speed_df": empty_df,
            "stint_summary_df": empty_df,
            "bestlap_summary_df": empty_df,
            "fastest_lap_row": None,
            "safety_laps": sorted(safety_laps),
            "driver_count": 0,
            "driver_labels": [],
            "session_meta": session_meta,
            "session_category": session_category,
            "is_sprint_session": is_sprint_session,
        }

    timing_df = pd.DataFrame(timing_rows).sort_values("seq").reset_index(drop=True)

    position_df = (
        timing_df.dropna(subset=["driver_no", "lap_number", "position"])
        .copy()
        .assign(
            lap_number=lambda d: d["lap_number"].astype(int),
            position=lambda d: d["position"].astype(int),
        )
        .drop_duplicates(subset=["driver_no", "lap_number"], keep="last")
        .sort_values(["driver_label", "lap_number", "seq"])
        .reset_index(drop=True)
    )
    pit_lap_df = position_df[position_df["in_pit"]].copy()

    gap_df = (
        position_df[
            [
                "driver_no",
                "driver_label",
                "team_color",
                "lap_number",
                "gap_to_leader_s",
                "gap_to_ahead_s",
            ]
        ]
        .dropna(subset=["gap_to_leader_s", "gap_to_ahead_s"], how="all")
        .sort_values(["driver_label", "lap_number"])
        .reset_index(drop=True)
    )

    bestlap_df = (
        timing_df.dropna(subset=["driver_no", "best_lap_lap", "best_lap_time_s"])
        .copy()
        .assign(best_lap_lap=lambda d: d["best_lap_lap"].astype(int))
        .drop_duplicates(subset=["driver_no", "best_lap_lap"], keep="last")
        .sort_values(["driver_label", "best_lap_lap", "seq"])
        .reset_index(drop=True)
    )

    speed_df = (
        timing_df.dropna(subset=["driver_no", "lap_number", "speed_trap_kph"])
        .copy()
        .assign(lap_number=lambda d: d["lap_number"].astype(int))
        .drop_duplicates(subset=["driver_no", "lap_number"], keep="last")
        .sort_values(["driver_label", "lap_number"])
        .reset_index(drop=True)
    )

    pace_df = (
        timing_df.dropna(subset=["driver_no", "lap_number", "last_lap_time_s"])
        .copy()
        .assign(lap_number=lambda d: d["lap_number"].astype(int))
        .drop_duplicates(subset=["driver_no", "lap_number"], keep="last")
    )
    pace_df = pace_df[~pace_df["in_pit"]].copy()
    pace_df = pace_df.sort_values(["driver_label", "lap_number"]).reset_index(drop=True)
    if not pace_df.empty:
        pace_df["rolling_2lap_s"] = (
            pace_df.groupby("driver_no")["last_lap_time_s"]
            .transform(lambda s: s.rolling(window=2, min_periods=1).mean())
        )
        pace_df["rolling_3lap_s"] = (
            pace_df.groupby("driver_no")["last_lap_time_s"]
            .transform(lambda s: s.rolling(window=3, min_periods=1).mean())
        )
        pace_df["clean_lap_index"] = pace_df.groupby("driver_no").cumcount() + 1

        if session_category == "race" and is_sprint_session:
            two_lap_mask = pace_df["clean_lap_index"] < SPRINT_WINDOW_SWITCH_LAP
            pace_df["rolling_race_pace_s"] = pace_df["rolling_3lap_s"]
            pace_df.loc[two_lap_mask, "rolling_race_pace_s"] = pace_df.loc[
                two_lap_mask, "rolling_2lap_s"
            ]
            pace_df["rolling_window"] = 3
            pace_df.loc[two_lap_mask, "rolling_window"] = 2
        else:
            pace_df["rolling_race_pace_s"] = pace_df["rolling_3lap_s"]
            pace_df["rolling_window"] = 3

        fastest_idx = pace_df["last_lap_time_s"].astype(float).idxmin()
        fastest_lap_row = pace_df.loc[fastest_idx].to_dict()
    else:
        fastest_lap_row = None

    latest_driver_df = (
        timing_df.dropna(subset=["driver_no"])
        .sort_values("seq")
        .drop_duplicates(subset=["driver_no"], keep="last")
        .reset_index(drop=True)
    )

    stint_driver_base = latest_driver_df[
        ["driver_no", "driver_label", "team_color", "number_of_pit_stops"]
    ].copy()
    stint_driver_base["number_of_pit_stops"] = pd.to_numeric(
        stint_driver_base["number_of_pit_stops"], errors="coerce"
    ).fillna(0).astype(int)

    completed_laps_df = (
        timing_df.dropna(subset=["driver_no", "lap_number"])
        .copy()
        .assign(lap_number=lambda d: pd.to_numeric(d["lap_number"], errors="coerce"))
        .dropna(subset=["lap_number"])
        .groupby("driver_no", as_index=False)["lap_number"]
        .max()
        .rename(columns={"lap_number": "completed_laps"})
    )
    if not completed_laps_df.empty:
        completed_laps_df["completed_laps"] = completed_laps_df["completed_laps"].astype(int)

    stint_summary_df = stint_driver_base.merge(
        completed_laps_df,
        on="driver_no",
        how="left",
    )
    stint_summary_df["completed_laps"] = pd.to_numeric(
        stint_summary_df["completed_laps"], errors="coerce"
    ).fillna(0).astype(int)
    stint_summary_df = stint_summary_df.rename(columns={"number_of_pit_stops": "pit_stops"})
    stint_summary_df = stint_summary_df[
        ["driver_no", "driver_label", "team_color", "completed_laps", "pit_stops"]
    ]

    if not pace_df.empty:
        best_clean = (
            pace_df.groupby("driver_no", as_index=False)["last_lap_time_s"]
            .min()
            .rename(columns={"last_lap_time_s": "best_clean_lap_s"})
        )
    else:
        best_clean = pd.DataFrame(columns=["driver_no", "best_clean_lap_s"])

    if not bestlap_df.empty:
        best_absolute = (
            bestlap_df.groupby("driver_no", as_index=False)["best_lap_time_s"]
            .min()
            .rename(columns={"best_lap_time_s": "best_lap_s"})
        )
    else:
        best_absolute = pd.DataFrame(columns=["driver_no", "best_lap_s"])

    if not speed_df.empty:
        max_speed = (
            speed_df.groupby("driver_no", as_index=False)["speed_trap_kph"]
            .max()
            .rename(columns={"speed_trap_kph": "max_speed_trap_kph"})
        )
    else:
        max_speed = pd.DataFrame(columns=["driver_no", "max_speed_trap_kph"])

    bestlap_summary_df = latest_driver_df[["driver_no", "driver_label", "team_color"]].copy()
    bestlap_summary_df = bestlap_summary_df.merge(best_clean, on="driver_no", how="left")
    bestlap_summary_df = bestlap_summary_df.merge(best_absolute, on="driver_no", how="left")
    bestlap_summary_df = bestlap_summary_df.merge(max_speed, on="driver_no", how="left")
    bestlap_summary_df = bestlap_summary_df.sort_values("driver_label").reset_index(drop=True)

    return {
        "timing_df": timing_df,
        "position_df": position_df,
        "pit_lap_df": pit_lap_df,
        "gap_df": gap_df,
        "pace_df": pace_df,
        "bestlap_df": bestlap_df,
        "speed_df": speed_df,
        "stint_summary_df": stint_summary_df,
        "bestlap_summary_df": bestlap_summary_df,
        "fastest_lap_row": fastest_lap_row,
        "safety_laps": sorted(safety_laps),
        "driver_count": int(latest_driver_df["driver_no"].nunique()) if not latest_driver_df.empty else 0,
        "driver_labels": sorted(latest_driver_df["driver_label"].dropna().unique().tolist()) if not latest_driver_df.empty else [],
        "session_meta": session_meta,
        "session_category": session_category,
        "is_sprint_session": is_sprint_session,
    }


def _build_session_meta(
    latest_session_info: dict[str, Any] | None,
    latest_session_status: str | None,
    track_status: str | None,
    track_message: str | None,
) -> dict[str, str]:
    session_info = latest_session_info or {}
    meeting_name = str(
        session_info.get("Meeting_Name")
        or session_info.get("Meeting_OfficialName")
        or "-"
    )
    session_name = str(session_info.get("Name") or session_info.get("Type") or "-")
    circuit_name = str(
        session_info.get("Meeting_Circuit_ShortName")
        or session_info.get("Meeting_Location")
        or "-"
    )
    country_name = str(session_info.get("Meeting_Country_Name") or "-")
    session_status = str(
        latest_session_status
        or session_info.get("SessionStatus")
        or "-"
    )
    track_status_value = str(track_status or "-")
    track_message_value = str(track_message or "-")

    return {
        "meeting_name": meeting_name,
        "session_name": session_name,
        "circuit_name": circuit_name,
        "country_name": country_name,
        "session_status": session_status,
        "track_status": track_status_value,
        "track_message": track_message_value,
    }


def _classify_session(session_meta: dict[str, str]) -> str:
    name = f"{session_meta.get('meeting_name', '')} {session_meta.get('session_name', '')}".lower()
    if any(token in name for token in ("qualifying", "shootout", "q1", "q2", "q3")):
        return "qualifying"
    if any(token in name for token in ("race", "sprint")) and "qualifying" not in name:
        return "race"
    return "practice"


def _is_sprint_session(session_meta: dict[str, str]) -> bool:
    session_name = str(session_meta.get("session_name") or "").lower()
    if not session_name:
        return False
    if "shootout" in session_name or "qualifying" in session_name:
        return False
    return "sprint" in session_name


class LiveSessionService:
    def __init__(self, max_events: int = 40000) -> None:
        self._lock = threading.Lock()
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self._seq_counter = itertools.count(1)
        self._thread: threading.Thread | None = None
        self._running = False
        self._started_at: str | None = None
        self._last_event_at: str | None = None
        self._last_error: str | None = None
        self._archive_snapshot: dict[str, Any] | None = None
        self._archive_loaded_at: str | None = None
        self._archive_session_path: str | None = None
        self._archive_error: str | None = None
        self._archive_last_attempt_at: str | None = None

    def start(self) -> bool:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._running = True
            self._last_error = None
            self._started_at = _utc_now_iso()
            self._thread = threading.Thread(
                target=self._run_client,
                name="livef1-session-thread",
                daemon=True,
            )
            self._thread.start()
            return True

    def _append_records(self, records: Any) -> None:
        if not isinstance(records, dict):
            return

        now = _utc_now_iso()
        with self._lock:
            for topic, payload_batch in records.items():
                payloads = payload_batch if isinstance(payload_batch, list) else [payload_batch]
                for payload in payloads:
                    self._events.append(
                        {
                            "seq": next(self._seq_counter),
                            "topic": str(topic),
                            "received_at": now,
                            "payload": payload,
                        }
                    )
            self._last_event_at = now

    def _run_client(self) -> None:
        try:
            from livef1.adapters import RealF1Client
            from livef1.data_processing.etl import function_map
        except Exception as exc:
            with self._lock:
                self._last_error = f"LiveF1 import failed: {exc}"
                self._running = False
            return

        compatible_topics = [
            topic for topic in SAFE_LIVE_TOPICS if callable(function_map.get(topic))
        ]
        if not compatible_topics:
            with self._lock:
                self._last_error = "No compatible LiveF1 topics found for this build."
                self._running = False
            return

        try:
            client = RealF1Client(topics=compatible_topics)

            @client.callback("dash_live_session")
            async def _live_handler(records):
                self._append_records(records)

            client.run()
        except Exception as exc:
            with self._lock:
                self._last_error = f"Live session stream crashed: {exc}"
        finally:
            with self._lock:
                self._running = False

    def _archive_cache_is_fresh(self) -> bool:
        if self._archive_snapshot is None or self._archive_loaded_at is None:
            return False
        loaded_at = _parse_utc_datetime(self._archive_loaded_at)
        if loaded_at is None:
            return False
        age_s = (datetime.now(timezone.utc) - loaded_at).total_seconds()
        return age_s <= ARCHIVE_CACHE_TTL_SECONDS

    def _archive_attempt_recent(self) -> bool:
        attempted_at = _parse_utc_datetime(self._archive_last_attempt_at)
        if attempted_at is None:
            return False
        age_s = (datetime.now(timezone.utc) - attempted_at).total_seconds()
        return age_s <= ARCHIVE_CACHE_TTL_SECONDS

    def _build_archive_events(self, session_path: str) -> list[dict[str, Any]]:
        from livef1.adapters.livetimingf1_adapter import (
            livetimingF1_getdata,
            livetimingF1_request,
        )
        from livef1.data_processing.etl import function_map

        normalized_path = str(session_path).strip()
        if not normalized_path:
            raise RuntimeError("Archive session path is empty.")
        if not normalized_path.endswith("/"):
            normalized_path = f"{normalized_path}/"

        session_index = livetimingF1_request(urljoin(normalized_path, "Index.json"))
        feeds = session_index.get("Feeds")
        if not isinstance(feeds, dict):
            raise RuntimeError("Archive session index missing Feeds.")

        now = _utc_now_iso()
        seq = 1
        events: list[dict[str, Any]] = []
        topic_errors: list[str] = []

        for topic in SAFE_ARCHIVE_TOPICS:
            parser = function_map.get(topic)
            if not callable(parser):
                continue

            feed_info = feeds.get(topic)
            if not isinstance(feed_info, dict):
                continue

            use_stream = bool(topic in ARCHIVE_STREAM_TOPICS and feed_info.get("StreamPath"))
            feed_path = feed_info.get("StreamPath" if use_stream else "KeyFramePath")
            if not feed_path:
                feed_path = feed_info.get("KeyFramePath")
                use_stream = False
            if not feed_path:
                continue

            try:
                raw_payload = livetimingF1_getdata(
                    urljoin(normalized_path, feed_path),
                    stream=use_stream,
                )
                parse_input = raw_payload if use_stream else [(None, raw_payload)]
                parsed_records = list(parser(parse_input, None))
            except Exception as exc:
                topic_errors.append(f"{topic}: {exc}")
                continue

            for payload in parsed_records:
                if not isinstance(payload, dict):
                    continue
                events.append(
                    {
                        "seq": seq,
                        "topic": topic,
                        "received_at": now,
                        "payload": payload,
                    }
                )
                seq += 1

        if not events:
            details = "; ".join(topic_errors[:3]) if topic_errors else "no topics parsed"
            raise RuntimeError(f"No archive events parsed ({details}).")

        return events

    def _fetch_last_completed_archive_snapshot(self) -> dict[str, Any]:
        from livef1.adapters.livetimingf1_adapter import livetimingF1_request

        now_utc = datetime.now(timezone.utc)
        candidates: list[tuple[datetime, dict[str, Any]]] = []

        for year in (now_utc.year, now_utc.year - 1):
            try:
                season_payload = livetimingF1_request(f"{year}/Index.json")
            except Exception:
                continue
            selected = _select_last_completed_session(season_payload, now_utc)
            if selected is None:
                continue
            end_dt = _session_end_utc(selected["session"])
            if end_dt is None:
                continue
            candidates.append((end_dt, selected))

        if not candidates:
            raise RuntimeError("No completed LiveF1 session found in current/previous season index.")

        _, latest = max(candidates, key=lambda item: item[0])
        session_payload = latest["session"]
        meeting_payload = latest["meeting"]
        session_path = str(session_payload.get("Path") or "").strip()
        if not session_path:
            raise RuntimeError("Completed session found but path is missing.")

        events = self._build_archive_events(session_path)
        tables = _build_live_dataframes(events)

        fallback_meta = {
            "meeting_name": str(meeting_payload.get("Name") or "-"),
            "session_name": str(session_payload.get("Name") or session_payload.get("Type") or "-"),
            "circuit_name": str(
                (meeting_payload.get("Circuit") or {}).get("ShortName")
                or meeting_payload.get("Location")
                or "-"
            ),
            "country_name": str(
                (meeting_payload.get("Country") or {}).get("Name")
                or (meeting_payload.get("Country") or {}).get("Code")
                or "-"
            ),
            "session_status": str(
                session_payload.get("SessionStatus")
                or (session_payload.get("ArchiveStatus") or {}).get("Status")
                or "Complete"
            ),
            "track_status": "-",
            "track_message": "-",
        }

        if not tables["session_meta"].get("meeting_name") or tables["session_meta"]["meeting_name"] == "-":
            tables["session_meta"] = fallback_meta
            tables["session_category"] = _classify_session(fallback_meta)

        loaded_at = _utc_now_iso()
        return {
            "status": {
                "running": False,
                "started_at": None,
                "last_event_at": loaded_at,
                "last_error": None,
                "event_count": len(events),
                "source": "livef1_archive",
                "archive_loaded_at": loaded_at,
                "archive_session_path": session_path,
                "archive_cache_ttl_s": ARCHIVE_CACHE_TTL_SECONDS,
            },
            "source": "livef1_archive",
            **tables,
        }

    def _get_archive_snapshot(self, force_refresh: bool = False) -> dict[str, Any] | None:
        with self._lock:
            if not force_refresh and self._archive_cache_is_fresh():
                return self._archive_snapshot
            cached_snapshot = self._archive_snapshot
            if not force_refresh and cached_snapshot is None and self._archive_attempt_recent():
                return None
            self._archive_last_attempt_at = _utc_now_iso()

        try:
            archive_snapshot = self._fetch_last_completed_archive_snapshot()
        except Exception as exc:
            with self._lock:
                self._archive_error = f"Archive fallback failed: {exc}"
            return cached_snapshot

        with self._lock:
            self._archive_snapshot = archive_snapshot
            self._archive_loaded_at = archive_snapshot["status"].get("archive_loaded_at")
            self._archive_session_path = archive_snapshot["status"].get("archive_session_path")
            self._archive_error = None
        return archive_snapshot

    def snapshot(self, include_archive_fallback: bool = True) -> dict[str, Any]:
        with self._lock:
            events_copy = list(self._events)
            live_status = {
                "running": self._running and bool(self._thread and self._thread.is_alive()),
                "started_at": self._started_at,
                "last_event_at": self._last_event_at,
                "last_error": self._last_error,
                "event_count": len(self._events),
                "source": "live_stream",
            }
            archive_error = self._archive_error

        tables = _build_live_dataframes(events_copy)
        has_live_timing = not tables["timing_df"].empty

        last_event_dt = _parse_utc_datetime(live_status.get("last_event_at"))
        is_stale = True
        if last_event_dt is not None:
            is_stale = (datetime.now(timezone.utc) - last_event_dt).total_seconds() > LIVE_STALE_SECONDS

        session_status_text = str(
            (tables.get("session_meta") or {}).get("session_status") or ""
        ).strip().lower()
        session_ended = any(
            token in session_status_text
            for token in (
                "ends",
                "ended",
                "finalised",
                "finalized",
                "complete",
                "completed",
                "finished",
            )
        )

        should_archive_fallback = include_archive_fallback and (
            (not has_live_timing)
            or session_ended
        )

        if has_live_timing and not should_archive_fallback:
            live_status["stream_stale"] = is_stale
            live_status["session_ended"] = session_ended
            return {"status": live_status, "source": "live_stream", **tables}

        if should_archive_fallback:
            archive_snapshot = self._get_archive_snapshot(force_refresh=False)
            if archive_snapshot is not None:
                merged_status = dict(archive_snapshot.get("status", {}))
                merged_status["live_running"] = live_status["running"]
                merged_status["live_event_count"] = live_status["event_count"]
                merged_status["live_last_error"] = live_status["last_error"]
                merged_status["live_stream_stale"] = is_stale
                merged_status["live_session_ended"] = session_ended
                merged_status["source"] = "livef1_archive"
                return {
                    "status": merged_status,
                    "source": "livef1_archive",
                    **{
                        key: value
                        for key, value in archive_snapshot.items()
                        if key not in {"status", "source"}
                    },
                }

        if archive_error:
            live_status["archive_error"] = archive_error

        return {"status": live_status, "source": "live_stream", **tables}


live_session_service = LiveSessionService()
