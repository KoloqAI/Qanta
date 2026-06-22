from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Protocol


class MarketCalendar(Protocol):
    def is_trading_day(self, d: date) -> bool: ...
    def is_early_close(self, d: date) -> bool: ...
    def market_close_time(self, d: date) -> datetime: ...
    def next_trading_day(self, d: date) -> date: ...


class Scheduler(Protocol):
    async def schedule_job(self, name: str, cron: str, handler: str) -> dict: ...
    async def cancel_job(self, job_id: str) -> None: ...
    async def list_jobs(self) -> list[dict]: ...


# NYSE holidays (partial list -- covers major ones)
NYSE_HOLIDAYS_2024_2026 = {
    date(2024, 1, 1), date(2024, 1, 15), date(2024, 2, 19), date(2024, 3, 29),
    date(2024, 5, 27), date(2024, 6, 19), date(2024, 7, 4), date(2024, 9, 2),
    date(2024, 11, 28), date(2024, 12, 25),
    date(2025, 1, 1), date(2025, 1, 20), date(2025, 2, 17), date(2025, 4, 18),
    date(2025, 5, 26), date(2025, 6, 19), date(2025, 7, 4), date(2025, 9, 1),
    date(2025, 11, 27), date(2025, 12, 25),
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3),
    date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7),
    date(2026, 11, 26), date(2026, 12, 25),
}

NYSE_EARLY_CLOSES = {
    date(2024, 7, 3), date(2024, 11, 29), date(2024, 12, 24),
    date(2025, 7, 3), date(2025, 11, 28), date(2025, 12, 24),
    date(2026, 11, 27), date(2026, 12, 24),
}


class MarketCalendarImpl:
    """NYSE market calendar. Deterministic."""

    def is_trading_day(self, d: date) -> bool:
        if d.weekday() >= 5:  # Sat/Sun
            return False
        return d not in NYSE_HOLIDAYS_2024_2026

    def is_early_close(self, d: date) -> bool:
        return d in NYSE_EARLY_CLOSES

    def market_close_time(self, d: date) -> datetime:
        if self.is_early_close(d):
            return datetime.combine(d, time(13, 0))  # 1:00 PM ET
        return datetime.combine(d, time(16, 0))  # 4:00 PM ET

    def next_trading_day(self, d: date) -> date:
        candidate = d + timedelta(days=1)
        while not self.is_trading_day(candidate):
            candidate += timedelta(days=1)
        return candidate


class SchedulerImpl:
    """In-memory job scheduler."""

    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._counter = 0

    async def schedule_job(self, name: str, cron: str, handler: str) -> dict:
        import uuid
        job_id = str(uuid.uuid4())
        self._jobs[job_id] = {
            "id": job_id,
            "name": name,
            "cron": cron,
            "handler": handler,
            "active": True,
        }
        return self._jobs[job_id]

    async def cancel_job(self, job_id: str) -> None:
        if job_id in self._jobs:
            self._jobs[job_id]["active"] = False

    async def list_jobs(self) -> list[dict]:
        return list(self._jobs.values())


class EODFlattenJob:
    """Flattens all intraday positions before market close.

    Deterministic. No LLM. Checks market calendar, flattens via broker
    when within the flatten window.
    """

    def __init__(
        self,
        broker: Any,
        calendar: MarketCalendar,
        flatten_minutes_before_close: int = 5,
        audit_log: Any = None,
    ) -> None:
        self._broker = broker
        self._calendar = calendar
        self._flatten_minutes_before_close = flatten_minutes_before_close
        self._audit_log = audit_log

    async def check_and_flatten(self, current_time: datetime | None = None) -> dict:
        """Check if we're in the flatten window and flatten if so.

        Returns a dict with keys: flattened (bool), reason (str), close_time, current_time
        """
        now = current_time or datetime.now()
        today = now.date()

        # Check if today is a trading day
        if not self._calendar.is_trading_day(today):
            return {
                "flattened": False,
                "reason": f"{today} is not a trading day",
                "close_time": None,
                "current_time": now,
            }

        close_time = self._calendar.market_close_time(today)
        flatten_start = close_time - timedelta(minutes=self._flatten_minutes_before_close)

        # Check if current time is within the flatten window
        if flatten_start <= now <= close_time:
            await self._broker.flatten_all()
            reason = (
                f"Flattened all positions: within {self._flatten_minutes_before_close}min "
                f"window before close at {close_time.strftime('%H:%M')}"
            )
            if self._audit_log is not None:
                self._audit_log.append({
                    "event": "eod_flatten",
                    "time": now.isoformat(),
                    "close_time": close_time.isoformat(),
                    "reason": reason,
                })
            return {
                "flattened": True,
                "reason": reason,
                "close_time": close_time,
                "current_time": now,
            }

        return {
            "flattened": False,
            "reason": f"Outside flatten window (flatten starts at {flatten_start.strftime('%H:%M')})",
            "close_time": close_time,
            "current_time": now,
        }
