from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np
import pandas as pd

from app.core.dsl.schema import StrategySpec
from app.core.dsl.interpreter import interpret


@dataclass
class CostModel:
    commission_per_share: float = 0.005
    spread_bps: float = 5.0
    slippage_bps: float = 2.0

    def total_cost_per_share(self, price: float) -> float:
        spread_cost = price * self.spread_bps / 10_000
        slippage_cost = price * self.slippage_bps / 10_000
        return self.commission_per_share + spread_cost + slippage_cost


@dataclass
class DateWindow:
    start: str
    end: str


@dataclass
class Trade:
    entry_date: str
    exit_date: str
    symbol: str
    side: str  # "long" | "short"
    entry_price: float
    exit_price: float
    shares: float
    pnl_gross: float
    pnl_net: float
    cost: float
    exit_reason: str  # "stop_loss" | "take_profit" | "time_stop" | "regime_break" | "end_of_data"


@dataclass
class BacktestResult:
    sharpe: float
    max_drawdown: float
    net_edge: float
    frictionless_edge: float
    n_trades: int
    equity_curve: list[dict[str, Any]]
    trades: list[Trade] = field(default_factory=list)
    total_return: float = 0.0
    win_rate: float = 0.0


class Backtester(Protocol):
    async def run(self, spec: dict, window: DateWindow, costs: CostModel) -> BacktestResult: ...


class BacktesterImpl:
    """Event-driven backtester. Evaluates signals bar-by-bar.

    Default fill: next-bar open. Reports frictionless vs net edge.
    No LLM, no broker, deterministic.
    """

    def __init__(self, initial_capital: float = 100_000.0) -> None:
        self._initial_capital = initial_capital

    async def run(
        self,
        spec: StrategySpec,
        bars: pd.DataFrame,
        costs: CostModel | None = None,
    ) -> BacktestResult:
        if costs is None:
            costs = CostModel()

        signals = interpret(spec, bars)
        return self._simulate(spec, bars, signals, costs)

    def _simulate(
        self,
        spec: StrategySpec,
        bars: pd.DataFrame,
        signals: pd.DataFrame,
        costs: CostModel,
    ) -> BacktestResult:
        capital = self._initial_capital
        position: dict[str, Any] | None = None
        trades: list[Trade] = []
        equity_curve: list[dict[str, Any]] = []
        daily_returns_gross: list[float] = []
        daily_returns_net: list[float] = []

        dates = bars.index.tolist()
        time_stop_bars = _get_time_stop(spec)

        for i in range(len(dates)):
            date = dates[i]
            bar = bars.iloc[i]
            sig = signals.iloc[i]
            prev_equity = capital + (self._position_value(position, bar) if position else 0)

            # Check exits if in a position
            if position is not None:
                exit_reason = self._check_exits(position, bar, sig, i, time_stop_bars)
                if exit_reason:
                    exit_price = bar["open"]  # fill at next-bar open (this bar's open)
                    trade = self._close_position(position, exit_price, date, costs, exit_reason)
                    trades.append(trade)
                    capital += trade.pnl_net
                    daily_returns_gross.append(trade.pnl_gross / self._initial_capital)
                    daily_returns_net.append(trade.pnl_net / self._initial_capital)
                    position = None
                else:
                    daily_returns_gross.append(0.0)
                    daily_returns_net.append(0.0)
            else:
                daily_returns_gross.append(0.0)
                daily_returns_net.append(0.0)

            # Check entry signals (only if flat)
            if position is None and sig["signal"] != 0 and i < len(dates) - 1:
                next_bar = bars.iloc[i + 1]
                entry_price = next_bar["open"]  # fill at next-bar open
                size_pct = sig["position_size_pct"]
                if size_pct > 0:
                    position_value = capital * (size_pct / 100.0)
                    shares = position_value / entry_price
                    position = {
                        "entry_date": dates[i + 1],
                        "entry_price": entry_price,
                        "shares": shares,
                        "side": "long" if sig["signal"] == 1 else "short",
                        "stop_loss": sig["stop_loss"],
                        "take_profit": sig["take_profit"],
                        "entry_bar_idx": i + 1,
                        "symbol": spec.tickers[0] if spec.tickers else "UNKNOWN",
                    }

            curr_equity = capital + (self._position_value(position, bar) if position else 0)
            equity_curve.append({"date": str(date.date()) if hasattr(date, 'date') else str(date), "equity": round(curr_equity, 2)})

        # Close any remaining position at end
        if position is not None:
            last_bar = bars.iloc[-1]
            trade = self._close_position(position, last_bar["close"], dates[-1], costs, "end_of_data")
            trades.append(trade)
            capital += trade.pnl_net

        return self._build_result(trades, equity_curve, daily_returns_gross, daily_returns_net)

    def _position_value(self, position: dict, bar: pd.Series) -> float:
        if position["side"] == "long":
            return position["shares"] * (bar["close"] - position["entry_price"])
        else:
            return position["shares"] * (position["entry_price"] - bar["close"])

    def _check_exits(
        self, position: dict, bar: pd.Series, sig: pd.Series, bar_idx: int, time_stop_bars: int | None
    ) -> str | None:
        side = position["side"]

        # Stop loss
        stop = position.get("stop_loss")
        if stop is not None and not np.isnan(stop):
            if side == "long" and bar["low"] <= stop:
                return "stop_loss"
            if side == "short" and bar["high"] >= stop:
                return "stop_loss"

        # Take profit
        tp = position.get("take_profit")
        if tp is not None and not np.isnan(tp):
            if side == "long" and bar["high"] >= tp:
                return "take_profit"
            if side == "short" and bar["low"] <= tp:
                return "take_profit"

        # Time stop
        if time_stop_bars is not None:
            bars_held = bar_idx - position["entry_bar_idx"]
            if bars_held >= time_stop_bars:
                return "time_stop"

        # Regime break
        if not sig.get("regime_active", True):
            return "regime_break"

        return None

    def _close_position(
        self, position: dict, exit_price: float, exit_date: Any, costs: CostModel, reason: str
    ) -> Trade:
        shares = position["shares"]
        entry_price = position["entry_price"]

        if position["side"] == "long":
            pnl_gross = shares * (exit_price - entry_price)
        else:
            pnl_gross = shares * (entry_price - exit_price)

        cost = costs.total_cost_per_share(entry_price) * shares + costs.total_cost_per_share(exit_price) * shares
        pnl_net = pnl_gross - cost

        return Trade(
            entry_date=str(position["entry_date"]),
            exit_date=str(exit_date),
            symbol=position.get("symbol", ""),
            side=position["side"],
            entry_price=round(entry_price, 4),
            exit_price=round(exit_price, 4),
            shares=round(shares, 4),
            pnl_gross=round(pnl_gross, 2),
            pnl_net=round(pnl_net, 2),
            cost=round(cost, 2),
            exit_reason=reason,
        )

    def _build_result(
        self,
        trades: list[Trade],
        equity_curve: list[dict],
        daily_returns_gross: list[float],
        daily_returns_net: list[float],
    ) -> BacktestResult:
        n_trades = len(trades)
        if n_trades == 0:
            return BacktestResult(
                sharpe=0.0,
                max_drawdown=0.0,
                net_edge=0.0,
                frictionless_edge=0.0,
                n_trades=0,
                equity_curve=equity_curve,
                trades=trades,
            )

        # Returns
        gross_pnls = [t.pnl_gross for t in trades]
        net_pnls = [t.pnl_net for t in trades]
        total_gross = sum(gross_pnls)
        total_net = sum(net_pnls)
        frictionless_edge = total_gross / self._initial_capital
        net_edge = total_net / self._initial_capital

        # Win rate
        wins = sum(1 for p in net_pnls if p > 0)
        win_rate = wins / n_trades if n_trades > 0 else 0.0

        # Sharpe (annualized, from daily returns)
        net_arr = np.array(daily_returns_net)
        net_arr = net_arr[net_arr != 0]  # only days with activity
        if len(net_arr) > 1:
            sharpe = (net_arr.mean() / net_arr.std()) * np.sqrt(252) if net_arr.std() > 0 else 0.0
        else:
            sharpe = 0.0

        # Max drawdown from equity curve
        equities = [e["equity"] for e in equity_curve]
        max_dd = self._max_drawdown(equities)

        return BacktestResult(
            sharpe=round(sharpe, 4),
            max_drawdown=round(max_dd, 4),
            net_edge=round(net_edge, 4),
            frictionless_edge=round(frictionless_edge, 4),
            n_trades=n_trades,
            equity_curve=equity_curve,
            trades=trades,
            total_return=round(net_edge, 4),
            win_rate=round(win_rate, 4),
        )

    @staticmethod
    def _max_drawdown(equities: list[float]) -> float:
        if not equities:
            return 0.0
        peak = equities[0]
        max_dd = 0.0
        for eq in equities:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        return max_dd


def _get_time_stop(spec: StrategySpec) -> int | None:
    for exit_spec in spec.exits:
        if "time_stop" in exit_spec:
            ts = exit_spec["time_stop"]
            if isinstance(ts, dict):
                return ts.get("sessions")
            return int(ts)
    return None
