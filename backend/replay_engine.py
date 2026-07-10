"""
replay_engine.py — Core replay logic for POST /v1/replay.

Fetches the original span from a stored trace, applies the user's
``edited_input`` overrides, and fires the reconstructed LLM call at the
provider's live API (OpenAI or Anthropic).

The user's provider API key is accepted per-request via a header and is
**never** persisted.

Backlog: 2.4.1
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------

_OPENAI_MODELS = frozenset(
    [
        "gpt-4",
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-3.5-turbo",
        "gpt-4-turbo",
        "o1",
        "o3",
    ]
)
_ANTHROPIC_MODELS = frozenset(
    [
        "claude-3-5-sonnet",
        "claude-3-5-haiku",
        "claude-3-opus",
        "claude-3-sonnet",
        "claude-3-haiku",
        "claude-2",
    ]
)


def _detect_provider(span_raw: dict) -> str:
    """
    Return ``"openai"`` or ``"anthropic"`` based on the span's model field.
    Raises HTTP 400 if the provider cannot be determined.
    """
    model: str = (span_raw.get("input") or {}).get("model") or ""
    model_lower = model.lower()

    for prefix in _ANTHROPIC_MODELS:
        if model_lower.startswith(prefix):
            return "anthropic"
    for prefix in _OPENAI_MODELS:
        if model_lower.startswith(prefix):
            return "openai"

    # Fall back: check trace-level source field
    source: str = span_raw.get("source", "")
    if source in ("anthropic",):
        return "anthropic"
    if source in ("openai",):
        return "openai"

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Cannot determine LLM provider for model '{model}'. "
        "Ensure the span's input.model field is set correctly.",
    )


# ---------------------------------------------------------------------------
# OpenAI replay
# ---------------------------------------------------------------------------


async def _call_openai(
    span_input: dict,
    edited_input: dict,
    provider_api_key: str,
) -> dict:
    """Fire the reconstructed call at the OpenAI chat completions API."""
    merged = {**span_input, **edited_input}

    model = merged.get("model", "gpt-4o-mini")
    messages = merged.get("messages", [])
    params = merged.get("params", {})
    tools = merged.get("tools", [])

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        **{
            k: v
            for k, v in params.items()
            if k in ("temperature", "max_tokens", "top_p")
        },
    }
    if tools:
        payload["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": t.get("name", ""),
                    "parameters": t.get("schema", {}),
                },
            }
            for t in tools
        ]

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {provider_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if resp.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenAI API key was rejected (401 Unauthorized).",
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI API returned {resp.status_code}: {resp.text[:500]}",
        )

    data = resp.json()
    choice = data["choices"][0]
    msg = choice["message"]
    return {
        "content": msg.get("content"),
        "tool_calls": [
            {
                "name": tc["function"]["name"],
                "arguments": json.loads(tc["function"]["arguments"] or "{}"),
            }
            for tc in (msg.get("tool_calls") or [])
        ],
        "model": data.get("model"),
        "usage": data.get("usage"),
    }


# ---------------------------------------------------------------------------
# Anthropic replay
# ---------------------------------------------------------------------------


async def _call_anthropic(
    span_input: dict,
    edited_input: dict,
    provider_api_key: str,
) -> dict:
    """Fire the reconstructed call at the Anthropic messages API."""
    merged = {**span_input, **edited_input}

    model = merged.get("model", "claude-3-5-haiku-20241022")
    messages = merged.get("messages", [])
    params = merged.get("params", {})
    tools = merged.get("tools", [])

    # Anthropic separates system messages from the messages list.
    system_content = ""
    chat_messages = []
    for m in messages:
        if m.get("role") == "system":
            system_content = m.get("content", "")
        else:
            chat_messages.append({"role": m["role"], "content": m["content"]})

    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": params.get("max_tokens", 1024),
        "messages": chat_messages,
    }
    if system_content:
        payload["system"] = system_content
    if "temperature" in params:
        payload["temperature"] = params["temperature"]
    if tools:
        payload["tools"] = [
            {
                "name": t.get("name", ""),
                "description": "",
                "input_schema": t.get("schema", {"type": "object", "properties": {}}),
            }
            for t in tools
        ]

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": provider_api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if resp.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Anthropic API key was rejected (401 Unauthorized).",
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Anthropic API returned {resp.status_code}: {resp.text[:500]}",
        )

    data = resp.json()
    text_blocks = [
        b["text"] for b in data.get("content", []) if b.get("type") == "text"
    ]
    tool_use_blocks = [
        {"name": b["name"], "arguments": b.get("input", {})}
        for b in data.get("content", [])
        if b.get("type") == "tool_use"
    ]
    return {
        "content": "\n".join(text_blocks) or None,
        "tool_calls": tool_use_blocks,
        "model": data.get("model"),
        "usage": data.get("usage"),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_replay(
    *,
    span_raw: dict,
    edited_input: dict,
    provider_api_key: str,
    source: str = "",
) -> dict:
    """
    Detect the provider, merge edits, call the live API, and return the
    replayed output dict.

    Parameters
    ----------
    span_raw:
        The raw span dict from the stored trace (the ``Span`` model dumped).
    edited_input:
        User-supplied overrides (messages, params, tools, etc.).
    provider_api_key:
        The caller's own LLM API key — never stored.
    source:
        Top-level trace source hint (e.g. ``"openai"``).
    """
    # Attach source hint for provider detection
    span_for_detection = {**span_raw, "source": source}
    provider = _detect_provider(span_for_detection)

    span_input = span_raw.get("input") or {}

    if provider == "openai":
        return await _call_openai(span_input, edited_input, provider_api_key)
    else:
        return await _call_anthropic(span_input, edited_input, provider_api_key)
