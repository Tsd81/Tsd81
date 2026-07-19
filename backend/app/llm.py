"""Swappable LLM provider interface.

- AnthropicProvider: real Claude via the Anthropic SDK (used when
  ANTHROPIC_API_KEY is set). Wrapped with timeout + retry.
- MockProvider: deterministic, offline fallback so the whole orchestrator
  runs and is verifiable without an API key. Used automatically when no key
  is present.

Select with get_provider(). The provider is the ONLY place that talks to an
LLM, so swapping vendors (or dropping in CrewAI) is a one-file change.
"""
from __future__ import annotations

import asyncio
import os
import textwrap
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    is_real: bool

    async def complete(self, system: str, prompt: str, max_tokens: int = 700) -> str:
        ...


class MockProvider:
    """Offline, deterministic. Produces plausible role-flavored text so the
    dashboard and pipeline work with no credentials."""

    name = "mock"
    is_real = False

    async def complete(self, system: str, prompt: str, max_tokens: int = 700) -> str:
        await asyncio.sleep(0.4)  # simulate think time so the graph animates
        role = _role_hint(system)
        head = prompt.strip().splitlines()[0][:140] if prompt.strip() else "the request"
        return textwrap.dedent(
            f"""\
            [{role} · offline mock] Working on: {head}

            • Assessed the request and outlined the key steps.
            • Produced a concise, actionable result for this role.
            • (Set ANTHROPIC_API_KEY to get real Claude output here.)"""
        )


class AnthropicProvider:
    """Real Claude. Imports the SDK lazily so the backend runs without it
    installed when only the mock is used."""

    name = "anthropic"
    is_real = True

    def __init__(self, api_key: str, model: str) -> None:
        from anthropic import AsyncAnthropic  # lazy

        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(self, system: str, prompt: str, max_tokens: int = 700) -> str:
        last_exc: Optional[Exception] = None
        for attempt in range(3):
            try:
                resp = await asyncio.wait_for(
                    self._client.messages.create(
                        model=self._model,
                        max_tokens=max_tokens,
                        system=system,
                        messages=[{"role": "user", "content": prompt}],
                    ),
                    timeout=60.0,
                )
                parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
                return "\n".join(parts).strip()
            except Exception as exc:  # timeout / rate limit / transient
                last_exc = exc
                await asyncio.sleep(2 ** attempt)
        raise RuntimeError(f"LLM call failed after retries: {last_exc}")


def _role_hint(system: str) -> str:
    first = (system or "").strip().splitlines()[0] if system else ""
    return first[:48] if first else "agent"


_provider: Optional[LLMProvider] = None


def get_provider() -> LLMProvider:
    """Singleton. Anthropic when a key is present, else the mock."""
    global _provider
    if _provider is not None:
        return _provider
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    model = os.getenv("MODEL", "claude-sonnet-4-5").strip()
    if key:
        try:
            _provider = AnthropicProvider(key, model)
            return _provider
        except Exception:
            # SDK missing or misconfigured → degrade to mock, never crash.
            pass
    _provider = MockProvider()
    return _provider
