"""LiteLLM-based LLM provider for research/analysis only.

SAFETY: This module must NEVER be imported from execution, risk, or portfolio
modules. LLM output informs research — it never places, sizes, or cancels orders.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Literal

import yaml

logger = logging.getLogger(__name__)


class LiteLLMProvider:
    """Routes LLM requests through LiteLLM with tier-based model selection and
    automatic fallback.

    Reads tier routing config from ``config/models.yaml``.  API keys are read
    from environment variables by litellm (OPENAI_API_KEY, ANTHROPIC_API_KEY,
    etc.) — they are never hardcoded here.
    """

    def __init__(self, config_path: str = "config/models.yaml") -> None:
        self._config = self._load_config(config_path)
        self._tiers: dict[str, dict[str, str]] = self._config.get("tiers", {})
        self._defaults: dict[str, Any] = self._config.get("defaults", {})
        self._rate_limits: dict[str, dict[str, int]] = self._config.get("rate_limits", {})

        # Simple per-tier sliding-window rate limiter: list of timestamps
        self._call_timestamps: dict[str, list[float]] = {
            tier: [] for tier in self._tiers
        }

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    @staticmethod
    def _load_config(config_path: str) -> dict[str, Any]:
        path = Path(config_path)
        if not path.exists():
            logger.warning("LLM config not found at %s — using empty defaults", config_path)
            return {}
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    async def _enforce_rate_limit(self, tier: str) -> None:
        """Block until the request fits within the per-tier RPM limit."""
        limits = self._rate_limits.get(tier)
        if not limits:
            return
        rpm = limits.get("rpm")
        if not rpm:
            return

        window = 60.0  # seconds
        timestamps = self._call_timestamps[tier]

        while True:
            now = time.monotonic()
            # Prune timestamps older than the window
            timestamps[:] = [ts for ts in timestamps if now - ts < window]
            if len(timestamps) < rpm:
                timestamps.append(now)
                return
            # Wait until the oldest call falls outside the window
            sleep_for = window - (now - timestamps[0]) + 0.05
            logger.debug("Rate-limited on tier %s — sleeping %.1fs", tier, sleep_for)
            await asyncio.sleep(sleep_for)

    # ------------------------------------------------------------------
    # Core completion
    # ------------------------------------------------------------------

    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tier: Literal["local", "mid", "frontier"] = "mid",
    ) -> dict:
        """Send a completion request via LiteLLM with automatic fallback.

        Tries the *primary* model for the requested tier first.  If that fails,
        retries with the *fallback* model.  If both fail, raises ``RuntimeError``
        with a clear diagnostic.
        """
        from litellm import acompletion  # deferred import to keep startup fast

        tier_cfg = self._tiers.get(tier)
        if tier_cfg is None:
            raise ValueError(
                f"Unknown LLM tier '{tier}'. Available tiers: {list(self._tiers)}"
            )

        primary_model = tier_cfg["primary"]
        fallback_model = tier_cfg.get("fallback")

        models_to_try = [primary_model]
        if fallback_model:
            models_to_try.append(fallback_model)

        last_error: Exception | None = None

        for model in models_to_try:
            try:
                await self._enforce_rate_limit(tier)

                call_kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": self._defaults.get("temperature", 0.3),
                    "max_tokens": self._defaults.get("max_tokens", 4096),
                    "timeout": self._defaults.get("timeout", 120),
                }
                if tools:
                    call_kwargs["tools"] = tools

                logger.info(
                    "LLM call  | tier=%s  model=%s  msg_count=%d",
                    tier,
                    model,
                    len(messages),
                )
                start = time.monotonic()
                response = await acompletion(**call_kwargs)
                elapsed = time.monotonic() - start
                logger.info(
                    "LLM done  | tier=%s  model=%s  elapsed=%.2fs",
                    tier,
                    model,
                    elapsed,
                )

                return self._normalise_response(response)

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "LLM call failed  | tier=%s  model=%s  error=%s: %s",
                    tier,
                    model,
                    type(exc).__name__,
                    exc,
                )
                if model != models_to_try[-1]:
                    logger.info("Falling back to next model for tier '%s'", tier)

        # Both primary and fallback failed
        raise RuntimeError(
            f"All models for tier '{tier}' failed. "
            f"Tried: {models_to_try}. Last error: {last_error}"
        ) from last_error

    # ------------------------------------------------------------------
    # Response normalisation
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_response(response: Any) -> dict:
        """Convert a litellm ``ModelResponse`` into a plain dict matching the
        ``LLMProvider`` protocol contract."""
        choice = response.choices[0]
        message = choice.message

        tool_calls: list[dict] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                )

        return {
            "role": message.role or "assistant",
            "content": message.content or "",
            "tool_calls": tool_calls,
        }
