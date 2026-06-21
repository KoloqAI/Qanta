from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Order:
    symbol: str
    side: str  # buy | sell
    qty: float
    order_type: str  # market | limit
    limit_price: float | None = None
    stop_price: float | None = None
    bracket_stop: float | None = None
    bracket_tp: float | None = None


@dataclass
class OrderAck:
    order_id: str
    status: str
    message: str = ""


class Broker(Protocol):
    async def submit(self, order: Order) -> OrderAck: ...
    async def cancel(self, order_id: str) -> OrderAck: ...
    async def flatten_all(self) -> None: ...
    async def positions(self) -> list[dict]: ...
    async def reconcile(self) -> dict: ...


class ExecutionRuntime(Protocol):
    async def start(self, deployment_id: str) -> None: ...
    async def stop(self, deployment_id: str) -> None: ...
    async def heartbeat(self) -> bool: ...


class PaperBroker:
    """Simulated broker for paper trading. No real orders."""

    def __init__(self) -> None:
        self._orders: dict[str, dict[str, Any]] = {}
        self._positions: dict[str, dict[str, Any]] = {}
        self._fills: list[dict] = []

    async def submit(self, order: Order) -> OrderAck:
        order_id = str(uuid.uuid4())
        self._orders[order_id] = {
            "order_id": order_id,
            "symbol": order.symbol,
            "side": order.side,
            "qty": order.qty,
            "order_type": order.order_type,
            "status": "filled",
            "bracket_stop": order.bracket_stop,
            "bracket_tp": order.bracket_tp,
        }

        # Update positions
        current = self._positions.get(order.symbol, {"qty": 0.0, "side": None})
        if order.side == "buy":
            current["qty"] += order.qty
            current["side"] = "long"
        else:
            current["qty"] -= order.qty
            if current["qty"] <= 0:
                current["qty"] = abs(current["qty"])
                current["side"] = "short" if current["qty"] > 0 else None

        if current["qty"] > 0:
            self._positions[order.symbol] = current
        else:
            self._positions.pop(order.symbol, None)

        self._fills.append({
            "order_id": order_id,
            "symbol": order.symbol,
            "side": order.side,
            "qty": order.qty,
        })

        return OrderAck(order_id=order_id, status="filled", message="Paper fill")

    async def cancel(self, order_id: str) -> OrderAck:
        if order_id in self._orders:
            self._orders[order_id]["status"] = "cancelled"
            return OrderAck(order_id=order_id, status="cancelled")
        return OrderAck(order_id=order_id, status="error", message="Order not found")

    async def flatten_all(self) -> None:
        for symbol, pos in list(self._positions.items()):
            side = "sell" if pos["side"] == "long" else "buy"
            await self.submit(Order(symbol=symbol, side=side, qty=pos["qty"], order_type="market"))
        self._positions.clear()

    async def positions(self) -> list[dict]:
        return [
            {"symbol": sym, **pos}
            for sym, pos in self._positions.items()
        ]

    async def reconcile(self) -> dict:
        return {"status": "ok", "positions": await self.positions()}


class ExecutionRuntimeImpl:
    """Manages deployment lifecycle. Deterministic -- no LLM."""

    def __init__(self, broker: Broker, risk_gate: Any, portfolio_gate: Any) -> None:
        self._broker = broker
        self._risk_gate = risk_gate
        self._portfolio_gate = portfolio_gate
        self._active: dict[str, bool] = {}
        self._heartbeat_ok = True

    async def start(self, deployment_id: str) -> None:
        self._active[deployment_id] = True

    async def stop(self, deployment_id: str) -> None:
        self._active.pop(deployment_id, None)

    async def heartbeat(self) -> bool:
        return self._heartbeat_ok

    async def submit_order(self, order: Order, book_state: Any, portfolio: dict) -> OrderAck:
        """Full order flow: RiskGate -> PortfolioRiskGate -> Broker."""
        # Per-order risk gate
        risk_decision = self._risk_gate.check(
            {"symbol": order.symbol, "side": order.side, "qty": order.qty,
             "order_type": order.order_type, "stop_price": order.stop_price,
             "bracket_stop": order.bracket_stop},
            book_state,
        )
        if not risk_decision.allowed:
            return OrderAck(order_id="", status="rejected", message=f"RiskGate: {risk_decision.reason}")

        # Portfolio-level risk gate
        port_decision = self._portfolio_gate.check(
            {"symbol": order.symbol, "side": order.side, "qty": order.qty},
            portfolio,
        )
        if not port_decision["allowed"]:
            return OrderAck(order_id="", status="rejected", message=f"PortfolioGate: {port_decision['reason']}")

        return await self._broker.submit(order)
