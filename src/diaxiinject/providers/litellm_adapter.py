"""LiteLLM-based universal adapter for any supported provider."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import litellm

from diaxiinject.models import Response
from diaxiinject.providers.base import TargetAdapter

logger = logging.getLogger(__name__)

# Suppress litellm's noisy default logging
litellm.suppress_debug_info = True

# Approximate USD-to-AUD conversion factor (updated periodically)
_USD_TO_AUD = 1.55


class _TokenBucket:
    """Simple token-bucket rate limiter for requests-per-minute."""

    def __init__(self, rpm: int) -> None:
        self._rpm = max(rpm, 1)
        self._interval = 60.0 / self._rpm
        self._last_request: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a request token is available."""
        async with self._lock:
            now = time.monotonic()
            wait = self._interval - (now - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()


class LiteLLMAdapter(TargetAdapter):
    """Universal target adapter powered by LiteLLM.

    Works with OpenAI, Anthropic, Google, Azure, Bedrock, Mistral, and
    every other provider that LiteLLM supports.

    Parameters
    ----------
    provider:
        Logical provider name (e.g. ``"openai"``, ``"anthropic"``).
    model:
        LiteLLM model string (e.g. ``"gpt-5.4"``, ``"claude-sonnet-4-6"``).
    api_key:
        Provider API key. Falls back to the environment variable LiteLLM
        expects for the provider.
    system_message:
        Optional persistent system prompt prepended to every request.
    rpm:
        Maximum requests per minute (rate-limited via a token bucket).
    max_retries:
        Maximum number of retry attempts on transient errors.
    extra_params:
        Arbitrary extra keyword arguments forwarded to ``litellm.acompletion``.
    """

    def __init__(
        self,
        provider: str,
        model: str,
        *,
        api_key: str | None = None,
        system_message: str | None = None,
        rpm: int = 60,
        max_retries: int = 3,
        **extra_params: Any,
    ) -> None:
        super().__init__(provider=provider, model=model)
        self._api_key = api_key
        self._system_message = system_message
        self._max_retries = max_retries
        self._extra_params = extra_params
        self._bucket = _TokenBucket(rpm)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_messages(
        self,
        message: str,
        conversation_id: str | None,
    ) -> tuple[str, list[dict[str, str]]]:
        """Build the messages list and return (conversation_id, messages)."""
        if conversation_id is None:
            conversation_id = self.new_conversation()

        history = self._get_history(conversation_id)

        messages: list[dict[str, str]] = []
        if self._system_message:
            messages.append({"role": "system", "content": self._system_message})
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        return conversation_id, messages

    async def _call_litellm(
        self,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None,
    ) -> Any:
        """Call litellm.acompletion with retries and rate limiting."""
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            await self._bucket.acquire()
            try:
                kwargs: dict[str, Any] = {
                    "model": self.model,
                    "messages": messages,
                    **self._extra_params,
                }
                if self._api_key:
                    kwargs["api_key"] = self._api_key
                if tools:
                    kwargs["tools"] = tools

                return await litellm.acompletion(**kwargs)

            except (
                litellm.RateLimitError,
                litellm.ServiceUnavailableError,
                litellm.Timeout,
                litellm.APIConnectionError,
            ) as exc:
                last_error = exc
                backoff = 2 ** (attempt - 1)
                logger.warning(
                    "LiteLLM transient error (attempt %d/%d): %s - retrying in %ds",
                    attempt,
                    self._max_retries,
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)

            except litellm.APIError as exc:
                # Non-transient API errors should not be retried
                raise RuntimeError(
                    f"LiteLLM API error for {self.model}: {exc}"
                ) from exc

        raise RuntimeError(
            f"LiteLLM request failed after {self._max_retries} retries: {last_error}"
        )

    def _parse_response(
        self,
        raw_response: Any,
        conversation_id: str,
    ) -> Response:
        """Convert a LiteLLM response object into our Response model."""
        choice = raw_response.choices[0]
        text = choice.message.content or ""

        usage: dict[str, int] = {}
        if raw_response.usage:
            usage = {
                "prompt_tokens": raw_response.usage.prompt_tokens or 0,
                "completion_tokens": raw_response.usage.completion_tokens or 0,
                "total_tokens": raw_response.usage.total_tokens or 0,
            }

        cost_usd = self._compute_cost(raw_response)
        cost_aud = cost_usd * _USD_TO_AUD

        return Response(
            text=text,
            model=self.model,
            provider=self.provider,
            conversation_id=conversation_id,
            finish_reason=choice.finish_reason,
            usage=usage,
            raw=raw_response.model_dump() if hasattr(raw_response, "model_dump") else {},
            cost_aud=cost_aud,
        )

    @staticmethod
    def _compute_cost(raw_response: Any) -> float:
        """Compute cost in USD using litellm's cost helper."""
        try:
            return litellm.completion_cost(completion_response=raw_response) or 0.0
        except Exception:
            # Some models may lack pricing data
            return 0.0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def send_message(
        self,
        message: str,
        conversation_id: str | None = None,
    ) -> Response:
        conversation_id, messages = self._build_messages(message, conversation_id)

        raw = await self._call_litellm(messages)
        response = self._parse_response(raw, conversation_id)

        # Track history for multi-turn
        self._append_message(conversation_id, "user", message)
        self._append_message(conversation_id, "assistant", response.text)

        return response

    async def send_with_tools(
        self,
        message: str,
        tools: list[dict],
        conversation_id: str | None = None,
    ) -> Response:
        conversation_id, messages = self._build_messages(message, conversation_id)

        raw = await self._call_litellm(messages, tools=tools)
        response = self._parse_response(raw, conversation_id)

        self._append_message(conversation_id, "user", message)
        self._append_message(conversation_id, "assistant", response.text)

        return response

    def get_cost_estimate(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in AUD for given token counts."""
        try:
            cost_usd = litellm.completion_cost(
                model=self.model,
                prompt="x",  # dummy - litellm needs something
                completion="x",
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
            )
            return (cost_usd or 0.0) * _USD_TO_AUD
        except Exception:
            return 0.0
