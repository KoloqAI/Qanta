from __future__ import annotations

import json
import logging
from typing import Any, Literal, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol definitions
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Stub provider (dev / offline fallback)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------


def create_llm_provider() -> LLMProvider:
    """Create LLM provider.

    Uses LiteLLM if any API key is configured, otherwise falls back to the
    stub so that everything works without credentials during development.
    """
    from app.config import settings

    if settings.anthropic_api_key or settings.openai_api_key or settings.gemini_api_key:
        from app.modules.research.llm_provider import LiteLLMProvider

        logger.info("Using LiteLLMProvider (API key detected)")
        return LiteLLMProvider()

    logger.info("No LLM API keys configured — using StubLLMProvider")
    return StubLLMProvider()


# ---------------------------------------------------------------------------
# Research domain: Short-term US equity
# ---------------------------------------------------------------------------


class ShortTermEquityDomain:
    """Research domain for short-term US equity strategies."""

    name = "short_term_equity"

    def __init__(self, llm: LLMProvider | None = None) -> None:
        self._llm = llm

    async def scan(self, goal: str, context: dict) -> list[dict]:
        from app.modules.data.providers import create_data_provider

        provider = create_data_provider()
        universe = await provider.universe()

        # When an LLM is available, ask it to score and rank candidates
        if self._llm and not isinstance(self._llm, StubLLMProvider):
            return await self._llm_scan(goal, universe, context)

        # Deterministic fallback
        return [{"ticker": t, "score": 0.5} for t in universe[:10]]

    async def _llm_scan(
        self, goal: str, universe: list[str], context: dict
    ) -> list[dict]:
        """Use the LLM to score tickers against the research goal."""
        assert self._llm is not None
        tickers_str = ", ".join(universe[:30])
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a quantitative equity research assistant. "
                    "Given a set of tickers and a research goal, return a JSON "
                    "array of objects with keys 'ticker' and 'score' (0-1). "
                    "Only include the top 10 tickers most relevant to the goal. "
                    "Return ONLY valid JSON, no markdown."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Research goal: {goal}\n"
                    f"Ticker universe: {tickers_str}\n"
                    f"Context: {json.dumps(context)}"
                ),
            },
        ]
        try:
            response = await self._llm.complete(messages, tier="local")
            content = response.get("content", "")
            candidates = json.loads(content)
            if isinstance(candidates, list):
                return candidates[:10]
        except Exception:
            logger.warning("LLM scan failed — falling back to deterministic scoring")
        # Fallback if LLM response is unparsable
        return [{"ticker": t, "score": 0.5} for t in universe[:10]]

    async def propose(self, ticker: str, context: dict) -> dict:
        # When an LLM is available, ask it to build a richer proposal
        if self._llm and not isinstance(self._llm, StubLLMProvider):
            return await self._llm_propose(ticker, context)

        # Deterministic fallback
        return {
            "ticker": ticker,
            "thesis": f"Mean-reversion opportunity in {ticker} within defined range",
            "regime": {"all_of": [{"gt": ["sma(50)", "sma(200)"]}]},
            "entry": {
                "when": {"crosses_above": ["sma(20)", "sma(50)"]},
                "action": "enter_long",
                "sizing": {"fixed_pct": {"pct": 5.0}},
            },
            "exits": [
                {"stop_loss": {"pct": 3.0}},
                {"take_profit": {"pct": 6.0}},
            ],
        }

    async def _llm_propose(self, ticker: str, context: dict) -> dict:
        """Use the LLM to generate a richer strategy proposal."""
        assert self._llm is not None
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a quantitative strategy designer. Given a ticker, "
                    "propose a short-term trading strategy as a JSON object with keys: "
                    "ticker, thesis, regime, entry, exits. "
                    "Use DSL expressions like sma(N), crosses_above, etc. "
                    "Return ONLY valid JSON, no markdown."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Ticker: {ticker}\n"
                    f"Context: {json.dumps(context)}"
                ),
            },
        ]
        try:
            response = await self._llm.complete(messages, tier="mid")
            content = response.get("content", "")
            proposal = json.loads(content)
            if isinstance(proposal, dict) and "ticker" in proposal:
                return proposal
        except Exception:
            logger.warning(
                "LLM propose failed for %s — falling back to template", ticker
            )
        # Deterministic fallback
        return {
            "ticker": ticker,
            "thesis": f"Mean-reversion opportunity in {ticker} within defined range",
            "regime": {"all_of": [{"gt": ["sma(50)", "sma(200)"]}]},
            "entry": {
                "when": {"crosses_above": ["sma(20)", "sma(50)"]},
                "action": "enter_long",
                "sizing": {"fixed_pct": {"pct": 5.0}},
            },
            "exits": [
                {"stop_loss": {"pct": 3.0}},
                {"take_profit": {"pct": 6.0}},
            ],
        }


# ---------------------------------------------------------------------------
# Strategy author
# ---------------------------------------------------------------------------


class StrategyAuthorImpl:
    """Composes DSL specs from thesis and intent. Uses tool catalog, not direct code."""

    def __init__(self, llm: LLMProvider | None = None) -> None:
        self._llm = llm

    async def author(self, thesis: str, intent: dict) -> dict:
        # When an LLM is available, use it to generate a richer spec
        if self._llm and not isinstance(self._llm, StubLLMProvider):
            return await self._llm_author(thesis, intent)

        # Deterministic / template fallback
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
                "sizing": {"fixed_pct": {"pct": 5.0}},
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

    async def _llm_author(self, thesis: str, intent: dict) -> dict:
        """Use the LLM to compose a full strategy spec from a thesis.

        Raises on LLM/parse failure — callers decide fallback policy.
        """
        assert self._llm is not None
        ticker = intent.get("ticker", "AAPL")
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a quantitative strategy author. Given a thesis and intent, "
                    "compose a complete strategy specification as a JSON object. "
                    "Required keys: id (empty string), version (1), tickers, thesis, "
                    "regime, entry, exits, risk, universe, validation. "
                    "Use DSL expressions (sma, ema, crosses_above, crosses_below, gt, lt). "
                    "Always include stop_loss, take_profit, and time_stop in exits. "
                    "Risk limits: max_position_pct, per_trade_stop_pct, max_gross_exposure. "
                    "Return ONLY valid JSON, no markdown."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Thesis: {thesis}\n"
                    f"Ticker: {ticker}\n"
                    f"Intent: {json.dumps(intent)}"
                ),
            },
        ]
        response = await self._llm.complete(messages, tier="mid")
        content = response.get("content", "")
        spec = json.loads(content)
        if not isinstance(spec, dict):
            raise ValueError("LLM returned non-dict response")
        spec.setdefault("id", "")
        spec.setdefault("version", 1)
        spec.setdefault("tickers", [ticker])
        spec.setdefault("thesis", thesis)
        return spec

    async def red_team(self, spec: dict) -> list[str]:
        # When an LLM is available, use it for deeper critique
        if self._llm and not isinstance(self._llm, StubLLMProvider):
            return await self._llm_red_team(spec)

        # Rule-based fallback
        return self._rule_based_red_team(spec)

    @staticmethod
    def _rule_based_red_team(spec: dict) -> list[str]:
        """Deterministic rule-based red-teaming."""
        concerns: list[str] = []
        if not spec.get("thesis"):
            concerns.append("Missing thesis")
        regime = spec.get("regime", {}).get("all_of", [])
        if len(regime) < 2:
            concerns.append("Regime has few conditions -- may be too broad")
        exits = spec.get("exits", [])
        if not any("time_stop" in e for e in exits):
            concerns.append("No time stop -- positions could be held indefinitely")
        return concerns

    async def _llm_red_team(self, spec: dict) -> list[str]:
        """Use the LLM to critically analyse a strategy spec."""
        assert self._llm is not None
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a critical quantitative strategy reviewer. "
                    "Analyse the following strategy specification for weaknesses, "
                    "risks, and potential issues. Return a JSON array of strings, "
                    "each string being one concern. Be thorough — consider regime "
                    "robustness, exit adequacy, risk limits, universe suitability, "
                    "and data-snooping risks. Return ONLY valid JSON, no markdown."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(spec, indent=2),
            },
        ]
        try:
            response = await self._llm.complete(messages, tier="mid")
            content = response.get("content", "")
            concerns = json.loads(content)
            if isinstance(concerns, list):
                # Merge with rule-based checks so we never miss structural issues
                rule_concerns = self._rule_based_red_team(spec)
                # Deduplicate while preserving order
                seen = set()
                merged: list[str] = []
                for c in rule_concerns + [str(c) for c in concerns]:
                    if c not in seen:
                        seen.add(c)
                        merged.append(c)
                return merged
        except Exception:
            logger.warning("LLM red-team failed — falling back to rule-based checks")
        return self._rule_based_red_team(spec)
