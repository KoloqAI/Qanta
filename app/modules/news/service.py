from __future__ import annotations

from typing import Any, Protocol


class NewsProvider(Protocol):
    async def search(self, ticker: str, window: dict) -> list[dict]: ...
    async def is_enabled(self) -> bool: ...


class NewsProviderStub:
    """Default off — optional module. Returns empty results."""

    async def search(self, ticker: str, window: dict) -> list[dict]:
        return []

    async def is_enabled(self) -> bool:
        return False
