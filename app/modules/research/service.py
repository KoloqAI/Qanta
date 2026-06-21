from __future__ import annotations

from typing import Any, Literal, Protocol


class LLMProvider(Protocol):
    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tier: Literal["local", "mid", "frontier"] = "mid",
    ) -> dict: ...


class ResearchDomain(Protocol):
    name: str

    async def scan(self, goal: str, context: dict) -> list[dict]: ...
    async def propose(self, ticker: str, context: dict) -> dict: ...


class StrategyAuthor(Protocol):
    async def author(self, thesis: str, intent: dict) -> dict: ...
    async def red_team(self, spec: dict) -> list[str]: ...


class StubLLMProvider:
    """Stub LLM provider for development. Returns template responses."""

    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tier: Literal["local", "mid", "frontier"] = "mid",
    ) -> dict:
        last_msg = messages[-1]["content"] if messages else ""
        return {
            "role": "assistant",
            "content": f"Analysis based on: {last_msg[:100]}",
            "tool_calls": [],
        }


class ShortTermEquityDomain:
    """Research domain for short-term US equity strategies."""

    name = "short_term_equity"

    async def scan(self, goal: str, context: dict) -> list[dict]:
        from app.modules.data.providers import SampleDataProvider

        provider = SampleDataProvider()
        universe = await provider.universe()
        return [{"ticker": t, "score": 0.5} for t in universe[:10]]

    async def propose(self, ticker: str, context: dict) -> dict:
        return {
            "ticker": ticker,
            "thesis": f"Mean-reversion opportunity in {ticker} within defined range",
            "regime": {"all_of": [{"gt": ["sma(50)", "sma(200)"]}]},
            "entry": {
                "when": {"crosses_above": ["sma(20)", "sma(50)"]},
                "action": "enter_long",
                "sizing": {"fixed_pct": 5.0},
            },
            "exits": [
                {"stop_loss": {"pct": 3.0}},
                {"take_profit": {"pct": 6.0}},
            ],
        }


class StrategyAuthorImpl:
    """Composes DSL specs from thesis and intent. Uses tool catalog, not direct code."""

    async def author(self, thesis: str, intent: dict) -> dict:
        ticker = intent.get("ticker", "AAPL")
        return {
            "id": "",
            "version": 1,
            "tickers": [ticker],
            "thesis": thesis,
            "regime": {"all_of": [{"gt": ["sma(50)", "sma(200)"]}]},
            "entry": {
                "when": {"crosses_above": ["sma(20)", "sma(50)"]},
                "action": "enter_long",
                "sizing": {"fixed_pct": 5.0},
            },
            "exits": [
                {"stop_loss": {"pct": 3.0}},
                {"take_profit": {"pct": 6.0}},
                {"time_stop": {"sessions": 10}},
            ],
            "risk": {
                "max_position_pct": 5.0,
                "per_trade_stop_pct": 3.0,
                "max_gross_exposure": 40.0,
            },
            "universe": {"primary": ticker},
            "validation": {"targets": [{"R": 0.02, "H": 7}]},
        }

    async def red_team(self, spec: dict) -> list[str]:
        concerns = []
        if not spec.get("thesis"):
            concerns.append("Missing thesis")
        regime = spec.get("regime", {}).get("all_of", [])
        if len(regime) < 2:
            concerns.append("Regime has few conditions -- may be too broad")
        exits = spec.get("exits", [])
        if not any("time_stop" in e for e in exits):
            concerns.append("No time stop -- positions could be held indefinitely")
        return concerns
