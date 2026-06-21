from __future__ import annotations

from typing import Any, Literal, Protocol


class Notifier(Protocol):
    async def send(
        self,
        event: str,
        severity: Literal["critical", "warning", "info"],
        payload: dict,
    ) -> None: ...

    async def test_channel(self, channel: str) -> bool: ...


class NotifierImpl:
    """Notification dispatcher. Routes events by severity to configured channels."""

    def __init__(self) -> None:
        self._log: list[dict[str, Any]] = []
        self._channels: dict[str, bool] = {"log": True}

    async def send(
        self, event: str, severity: Literal["critical", "warning", "info"], payload: dict
    ) -> None:
        entry = {"event": event, "severity": severity, "payload": payload}
        self._log.append(entry)

    async def test_channel(self, channel: str) -> bool:
        return channel in self._channels

    def get_log(self) -> list[dict[str, Any]]:
        return list(self._log)
