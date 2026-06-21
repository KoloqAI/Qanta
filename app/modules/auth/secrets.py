from __future__ import annotations

from typing import Any

from app.config import settings


BROKER_KEYS = {"ibkr_host", "ibkr_port", "ibkr_client_id"}
LLM_KEYS = {
    "ollama_base_url",
    "litellm_api_key",
    "openai_api_key",
    "anthropic_api_key",
    "gemini_api_key",
    "aws_bedrock_region",
}
NOTIFICATION_KEYS = {
    "ses_region",
    "ses_from_email",
    "telegram_bot_token",
    "telegram_chat_id",
}
ALL_SECRET_KEYS = BROKER_KEYS | LLM_KEYS | NOTIFICATION_KEYS | {"secret_key"}


def get_broker_secrets() -> dict[str, Any]:
    return {
        "ibkr_host": settings.ibkr_host,
        "ibkr_port": settings.ibkr_port,
        "ibkr_client_id": settings.ibkr_client_id,
    }


def get_llm_secrets() -> dict[str, str]:
    return {
        "ollama_base_url": settings.ollama_base_url,
        "litellm_api_key": settings.litellm_api_key,
        "openai_api_key": settings.openai_api_key,
        "anthropic_api_key": settings.anthropic_api_key,
        "gemini_api_key": settings.gemini_api_key,
        "aws_bedrock_region": settings.aws_bedrock_region,
    }


def redact_for_client(data: dict[str, Any]) -> dict[str, Any]:
    """Strip all secrets from a dict before sending to the client."""
    redacted = {}
    for key, value in data.items():
        if key.lower() in ALL_SECRET_KEYS:
            continue
        if isinstance(value, str) and any(
            s in key.lower() for s in ("key", "token", "secret", "password", "cred")
        ):
            redacted[key] = "***" if value else ""
        elif isinstance(value, dict):
            redacted[key] = redact_for_client(value)
        else:
            redacted[key] = value
    return redacted


def mask_connection_value(value: str) -> str:
    """Show only the last 4 characters of a secret for display."""
    if not value or len(value) <= 4:
        return "****"
    return "***" + value[-4:]
