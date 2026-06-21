from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class BookState:
    equity: float
    positions: list[dict]
    daily_pnl: float
    gross_exposure: float


@dataclass
class RiskDecision:
    allowed: bool
    reason: str = ""


class RiskGate(Protocol):
    def check(self, order: dict, book: BookState) -> RiskDecision: ...


class RiskGateImpl:
    """Per-order risk gate. Deterministic. No LLM. Fail closed."""

    def __init__(
        self,
        per_trade_stop_pct: float = 5.0,
        max_position_pct: float = 10.0,
        daily_drawdown_kill_pct: float = 5.0,
        pdt_equity_minimum: float = 25_000.0,
    ) -> None:
        self._per_trade_stop_pct = per_trade_stop_pct
        self._max_position_pct = max_position_pct
        self._daily_drawdown_kill_pct = daily_drawdown_kill_pct
        self._pdt_equity_minimum = pdt_equity_minimum
        self._killed = False

    def check(self, order: dict, book: BookState) -> RiskDecision:
        if self._killed:
            return RiskDecision(allowed=False, reason="Kill switch active -- all trading halted")

        # Daily drawdown kill switch
        if book.equity > 0:
            dd_pct = abs(book.daily_pnl) / book.equity * 100 if book.daily_pnl < 0 else 0
            if dd_pct >= self._daily_drawdown_kill_pct:
                self._killed = True
                return RiskDecision(
                    allowed=False,
                    reason=f"Daily drawdown {dd_pct:.1f}% >= kill threshold {self._daily_drawdown_kill_pct}%"
                )

        # Stop loss required
        if not order.get("bracket_stop") and not order.get("stop_price"):
            return RiskDecision(allowed=False, reason="No stop loss -- every position must have a stop")

        # Max position size
        if book.equity > 0:
            order_value = order.get("qty", 0) * order.get("price", 100)
            position_pct = (order_value / book.equity) * 100
            if position_pct > self._max_position_pct:
                return RiskDecision(
                    allowed=False,
                    reason=f"Position size {position_pct:.1f}% exceeds max {self._max_position_pct}%"
                )

        # PDT guard
        if order.get("horizon_mode") == "intraday" and book.equity < self._pdt_equity_minimum:
            return RiskDecision(
                allowed=False,
                reason=f"PDT: intraday trading requires ${self._pdt_equity_minimum:,.0f} equity (have ${book.equity:,.0f})"
            )

        return RiskDecision(allowed=True)

    def trigger_kill_switch(self) -> None:
        self._killed = True

    def reset_kill_switch(self) -> None:
        self._killed = False

    @property
    def is_killed(self) -> bool:
        return self._killed
