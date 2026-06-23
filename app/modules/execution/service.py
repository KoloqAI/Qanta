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


class DeploymentGateError(Exception):
    """Raised when a live deployment fails the safety gate checks."""
    pass


class ExecutionRuntime(Protocol):
    async def start(self, deployment_id: str, deployment_info: dict | None = None) -> None: ...
    async def stop(self, deployment_id: str) -> None: ...
    async def heartbeat(self) -> bool: ...


class PaperBroker:
    """Simulated broker for paper trading. No real orders."""

    def __init__(self) -> None:
        self._orders: dict[str, dict[str, Any]] = {}
        self._positions: dict[str, dict[str, Any]] = {}
        self._fills: list[dict] = []
        self._bracket_orders: dict[str, dict] = {}
        self._heartbeat_ok: bool = True

    def set_heartbeat(self, ok: bool) -> None:
        """Set heartbeat status. When False, new entries are blocked but
        protective bracket exits still execute."""
        self._heartbeat_ok = ok

    async def submit(self, order: Order) -> OrderAck:
        # Block new entries when heartbeat is lost
        if not self._heartbeat_ok:
            return OrderAck(
                order_id="",
                status="rejected",
                message="Heartbeat lost — entries blocked",
            )

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

        # Create bracket child orders if specified
        if order.bracket_stop is not None:
            bracket_id = str(uuid.uuid4())
            self._bracket_orders[bracket_id] = {
                "id": bracket_id,
                "parent_order_id": order_id,
                "symbol": order.symbol,
                "type": "stop",
                "trigger_price": order.bracket_stop,
                "qty": order.qty,
                "side": "sell" if order.side == "buy" else "buy",
                "status": "active",
            }

        if order.bracket_tp is not None:
            bracket_id = str(uuid.uuid4())
            self._bracket_orders[bracket_id] = {
                "id": bracket_id,
                "parent_order_id": order_id,
                "symbol": order.symbol,
                "type": "tp",
                "trigger_price": order.bracket_tp,
                "qty": order.qty,
                "side": "sell" if order.side == "buy" else "buy",
                "status": "active",
            }

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

    async def check_brackets(self, prices: dict[str, float]) -> list[dict]:
        """Check active bracket orders against current prices and trigger if hit.

        Bracket orders (protective exits) execute even when heartbeat is lost.

        Stop orders trigger when:
          - sell side (protecting long): price <= trigger_price
          - buy side (protecting short): price >= trigger_price

        TP orders trigger when:
          - sell side (closing long): price >= trigger_price
          - buy side (closing short): price <= trigger_price

        Returns list of triggered bracket orders.
        """
        triggered: list[dict] = []

        for bracket_id, bracket in list(self._bracket_orders.items()):
            if bracket["status"] != "active":
                continue

            symbol = bracket["symbol"]
            if symbol not in prices:
                continue

            price = prices[symbol]
            should_trigger = False

            if bracket["type"] == "stop":
                # Stop loss: sell triggers when price drops, buy triggers when price rises
                if bracket["side"] == "sell" and price <= bracket["trigger_price"]:
                    should_trigger = True
                elif bracket["side"] == "buy" and price >= bracket["trigger_price"]:
                    should_trigger = True

            elif bracket["type"] == "tp":
                # Take profit: sell triggers when price rises, buy triggers when price drops
                if bracket["side"] == "sell" and price >= bracket["trigger_price"]:
                    should_trigger = True
                elif bracket["side"] == "buy" and price <= bracket["trigger_price"]:
                    should_trigger = True

            if should_trigger:
                bracket["status"] = "triggered"
                # Execute the closing order directly (bypasses heartbeat check)
                close_order = Order(
                    symbol=bracket["symbol"],
                    side=bracket["side"],
                    qty=bracket["qty"],
                    order_type="market",
                )
                # Temporarily restore heartbeat to allow bracket execution
                saved_heartbeat = self._heartbeat_ok
                self._heartbeat_ok = True
                await self.submit(close_order)
                self._heartbeat_ok = saved_heartbeat
                triggered.append(bracket)

        return triggered

    async def get_bracket_orders(self) -> list[dict]:
        """Return all bracket orders (active and triggered)."""
        return list(self._bracket_orders.values())


class ExecutionRuntimeImpl:
    """Manages deployment lifecycle. Deterministic -- no LLM."""

    def __init__(
        self,
        broker: Broker,
        risk_gate: Any,
        portfolio_gate: Any,
        registry: Any | None = None,
        validation_store: Any | None = None,
    ) -> None:
        self._broker = broker
        self._risk_gate = risk_gate
        self._portfolio_gate = portfolio_gate
        self._registry = registry
        self._validation_store = validation_store
        self._active: dict[str, bool] = {}
        self._heartbeat_ok = True

    async def start(self, deployment_id: str, deployment_info: dict | None = None) -> None:
        if deployment_info is not None and deployment_info.get("mode") == "live":
            await self._enforce_deployment_gate(deployment_info)
        self._active[deployment_id] = True

    async def _enforce_deployment_gate(self, deployment_info: dict) -> None:
        """Check that a live deployment has passing validation AND approval."""
        strategy_id = deployment_info.get("strategy_id")
        if not strategy_id:
            raise DeploymentGateError(
                "Live deployment requires a strategy_id in deployment_info."
            )

        # Look up the strategy in the registry if available
        if self._registry is not None:
            strategy = await self._registry.get(strategy_id)
            if strategy is None:
                raise DeploymentGateError(
                    f"Strategy '{strategy_id}' not found in registry."
                )
            # Check that the strategy has been approved
            if strategy.get("status") == "approved":
                return  # Approved strategy passes the gate

        # Check validation_store for a passing report with current gates
        if self._validation_store is not None:
            from app.modules.validation.service import GATES_VERSION

            report = self._validation_store.get(strategy_id)
            if report is not None and report.get("passed"):
                if report.get("gates_version", 0) < GATES_VERSION:
                    raise DeploymentGateError(
                        f"Live deployment refused for strategy '{strategy_id}': "
                        f"validation report predates gates_version {GATES_VERSION} "
                        "(peer_hit gate added). Re-validate first."
                    )
                return  # Passing validation report passes the gate

        # Neither approval nor passing validation found
        raise DeploymentGateError(
            f"Live deployment refused for strategy '{strategy_id}': "
            "requires a passing ValidationReport AND human Approval "
            "bound to the strategy_version and user_id."
        )

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
