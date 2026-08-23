"""Thin OpenRouter chat completions client. Never raises, always degrades to None on failure."""
from __future__ import annotations

import logging
import os

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()  # picks up backend/.env if present; no-op otherwise

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# free tier catalog changes, override via OPENROUTER_MODEL if this dies
DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"

REQUEST_TIMEOUT_SECONDS = 20


def is_configured() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def complete_chat(messages: list[dict[str, str]], *, max_tokens: int = 500, temperature: float = 0.4) -> str | None:
    """OpenAI chat-format messages in, reply text or None out."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None

    model = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                # OpenRouter wants these for free-tier attribution, optional but nice to have
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "PortfolioLens",
            },
            json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:  # network/timeout/bad status/bad json, all treated the same
        logger.warning("OpenRouter completion failed (model=%s): %s", model, exc)
        return None
