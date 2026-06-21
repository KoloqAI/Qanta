from __future__ import annotations

from typing import Protocol


class Allocator(Protocol):
    def allocate(
        self,
        deployments: list[dict],
        equity: float,
        method: str = "fixed_fraction",
    ) -> dict[str, float]: ...


class PortfolioRiskGate(Protocol):
    def check(self, order: dict, portfolio: dict) -> dict: ...


class AllocatorImpl:
    """Deterministic capital allocation across deployments."""

    def __init__(self, cash_buffer_pct: float = 10.0, max_strategies: int = 10) -> None:
        self._cash_buffer_pct = cash_buffer_pct
        self._max_strategies = max_strategies

    def allocate(
        self, deployments: list[dict], equity: float, method: str = "fixed_fraction"
    ) -> dict[str, float]:
        if not deployments:
            return {}
        deployable = equity * (1 - self._cash_buffer_pct / 100)
        n = min(len(deployments), self._max_strategies)
        per_strategy = deployable / n if n > 0 else 0

        result = {}
        for d in deployments[:n]:
            dep_id = d.get("id", d.get("deployment_id", ""))
            if method == "fixed_fraction":
                result[dep_id] = round(per_strategy, 2)
            else:
                result[dep_id] = round(per_strategy, 2)
        return result


class PortfolioRiskGateImpl:
    """Aggregate portfolio-level risk gate. Deterministic. No LLM."""

    def __init__(
        self,
        max_gross_exposure_pct: float = 100.0,
        per_symbol_cap_pct: float = 20.0,
        max_strategies: int = 10,
    ) -> None:
        self._max_gross_exposure_pct = max_gross_exposure_pct
        self._per_symbol_cap_pct = per_symbol_cap_pct
        self._max_strategies = max_strategies

    def check(self, order: dict, portfolio: dict) -> dict:
        equity = portfolio.get("equity", 0)
        if equity <= 0:
            return {"allowed": False, "reason": "No equity"}

        # Gross exposure cap
        current_exposure = portfolio.get("gross_exposure", 0)
        order_value = order.get("qty", 0) * order.get("price", 100)
        new_exposure = current_exposure + order_value
        exposure_pct = (new_exposure / equity) * 100

        if exposure_pct > self._max_gross_exposure_pct:
            return {
                "allowed": False,
                "reason": f"Gross exposure {exposure_pct:.1f}% exceeds cap {self._max_gross_exposure_pct}%",
            }

        # Per-symbol aggregate cap
        symbol = order.get("symbol", "")
        symbol_exposure = portfolio.get("symbol_exposures", {}).get(symbol, 0)
        new_symbol_exp = symbol_exposure + order_value
        symbol_pct = (new_symbol_exp / equity) * 100

        if symbol_pct > self._per_symbol_cap_pct:
            return {
                "allowed": False,
                "reason": f"Symbol {symbol} exposure {symbol_pct:.1f}% exceeds cap {self._per_symbol_cap_pct}%",
            }

        # Max strategies
        active_count = portfolio.get("active_strategies", 0)
        if active_count >= self._max_strategies:
            return {
                "allowed": False,
                "reason": f"Max strategies ({self._max_strategies}) reached",
            }

        return {"allowed": True, "reason": ""}
