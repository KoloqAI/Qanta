from __future__ import annotations

from typing import Protocol


class HaltDetector(Protocol):
    def is_halted(self, symbol: str) -> bool: ...
    def halt_symbol(self, symbol: str, reason: str = "") -> None: ...
    def resume_symbol(self, symbol: str) -> None: ...
    def halted_symbols(self) -> dict[str, str]: ...


class HaltDetectorImpl:
    """Tracks LULD and other trading halts. Deterministic. No LLM."""

    def __init__(self) -> None:
        self._halted: dict[str, str] = {}  # symbol -> reason

    def is_halted(self, symbol: str) -> bool:
        return symbol in self._halted

    def halt_symbol(self, symbol: str, reason: str = "LULD halt") -> None:
        self._halted[symbol] = reason

    def resume_symbol(self, symbol: str) -> None:
        self._halted.pop(symbol, None)

    def halted_symbols(self) -> dict[str, str]:
        return dict(self._halted)
