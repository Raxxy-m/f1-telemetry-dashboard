from __future__ import annotations

from typing import Any

from data_engine import get_supported_event_schedule, load_session
from services.live_session_service import live_session_service
from services.style_service import extract_driver_styles


class FastF1Provider:
    def get_supported_event_schedule(self, year: int):
        return get_supported_event_schedule(year)

    def load_session(self, year: int, gp: int, session_type: int):
        return load_session(year, gp, session_type)

    def get_driver_styles(self, session, drivers):
        return extract_driver_styles(session, drivers)


class LiveF1Provider:
    def start_stream(self) -> bool:
        return live_session_service.start()

    def get_live_snapshot(self, include_archive_fallback: bool = True) -> dict[str, Any]:
        return live_session_service.snapshot(include_archive_fallback=include_archive_fallback)


class UnifiedTelemetryProvider:
    def __init__(
        self,
        fastf1_provider: FastF1Provider | None = None,
        livef1_provider: LiveF1Provider | None = None,
    ) -> None:
        self._fastf1 = fastf1_provider or FastF1Provider()
        self._livef1 = livef1_provider or LiveF1Provider()

    def get_supported_event_schedule(self, year: int):
        return self._fastf1.get_supported_event_schedule(year)

    def load_historical_session(self, year: int, gp: int, session_type: int):
        return self._fastf1.load_session(year, gp, session_type)

    def get_driver_styles(self, session, drivers):
        return self._fastf1.get_driver_styles(session, drivers)

    def start_live_stream(self) -> bool:
        return self._livef1.start_stream()

    def get_live_snapshot(self, include_archive_fallback: bool = True) -> dict[str, Any]:
        return self._livef1.get_live_snapshot(include_archive_fallback=include_archive_fallback)


telemetry_provider = UnifiedTelemetryProvider()
