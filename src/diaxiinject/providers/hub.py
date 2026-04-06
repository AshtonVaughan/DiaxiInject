"""Provider registry for target and attacker LLMs."""

from __future__ import annotations

import logging
from typing import Any

from diaxiinject.config import AttackerLLMConfig
from diaxiinject.providers.litellm_adapter import LiteLLMAdapter
from diaxiinject.providers.local_llm import LocalLLM

logger = logging.getLogger(__name__)

# Pre-configured provider shortcuts.
# Keys are friendly names; values map to the LiteLLM model prefix and any
# default kwargs needed for that provider.
_PROVIDER_SHORTCUTS: dict[str, dict[str, Any]] = {
    "openai": {
        "prefix": "",
        "defaults": {},
    },
    "anthropic": {
        "prefix": "",
        "defaults": {},
    },
    "google": {
        "prefix": "gemini/",
        "defaults": {},
    },
    "microsoft": {
        "prefix": "azure/",
        "defaults": {},
    },
    "meta": {
        "prefix": "together_ai/",
        "defaults": {},
    },
    "xai": {
        "prefix": "xai/",
        "defaults": {},
    },
    "mistral": {
        "prefix": "mistral/",
        "defaults": {},
    },
}


class ProviderHub:
    """Central registry for instantiating target and attacker LLMs.

    Usage::

        hub = ProviderHub()
        target = hub.get_target("openai", "gpt-5.4", api_key="sk-...")
        attacker = hub.get_attacker(AttackerLLMConfig())
    """

    def __init__(self) -> None:
        self._targets: dict[str, LiteLLMAdapter] = {}
        self._attackers: dict[str, LocalLLM] = {}

    # ------------------------------------------------------------------
    # Target adapters
    # ------------------------------------------------------------------

    # Default models per provider
    _DEFAULT_MODELS: dict[str, str] = {
        "openai": "gpt-5.4",
        "anthropic": "claude-sonnet-4-6",
        "google": "gemini-3.1-pro-preview",
        "microsoft": "gpt-5.4",
        "meta": "meta-llama/Llama-4-Maverick-17B-128E-Instruct",
        "xai": "grok-4.20",
        "mistral": "mistral-small-4",
    }

    def get_target(
        self,
        provider: str,
        model: str | None = None,
        api_key: str | None = None,
        *,
        system_message: str | None = None,
        rpm: int = 60,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> LiteLLMAdapter:
        """Return a :class:`LiteLLMAdapter` for the given provider/model.

        If a shortcut exists for *provider*, the model string is
        automatically prefixed so LiteLLM routes it correctly.
        Adapters are cached by ``(provider, model)`` so repeated calls
        with the same arguments return the same instance.
        """
        if model is None:
            model = self._DEFAULT_MODELS.get(provider.lower(), "gpt-5.4")
        cache_key = f"{provider}:{model}"
        if cache_key in self._targets:
            return self._targets[cache_key]

        litellm_model = self._resolve_model(provider, model)
        shortcut = _PROVIDER_SHORTCUTS.get(provider.lower(), {})
        merged_kwargs = {**shortcut.get("defaults", {}), **kwargs}

        adapter = LiteLLMAdapter(
            provider=provider,
            model=litellm_model,
            api_key=api_key,
            system_message=system_message,
            rpm=rpm,
            max_retries=max_retries,
            **merged_kwargs,
        )

        self._targets[cache_key] = adapter
        logger.info("Registered target adapter: %s -> %s", cache_key, litellm_model)
        return adapter

    @staticmethod
    def _resolve_model(provider: str, model: str) -> str:
        """Resolve a friendly provider + model into a LiteLLM model string."""
        shortcut = _PROVIDER_SHORTCUTS.get(provider.lower())
        if shortcut is None:
            # Unknown provider - pass through as-is; LiteLLM may still handle it
            return model

        prefix = shortcut["prefix"]
        # Avoid double-prefixing if the caller already included it
        if prefix and not model.startswith(prefix):
            return f"{prefix}{model}"
        return model

    # ------------------------------------------------------------------
    # Attacker / judge adapter
    # ------------------------------------------------------------------

    def get_attacker(self, config: AttackerLLMConfig) -> LocalLLM:
        """Return a :class:`LocalLLM` instance for the attacker model.

        Instances are cached by ``(backend, model, base_url)``.
        """
        cache_key = f"{config.backend}:{config.model}@{config.base_url}"
        if cache_key in self._attackers:
            return self._attackers[cache_key]

        attacker = LocalLLM(config)
        self._attackers[cache_key] = attacker
        logger.info("Registered attacker LLM: %s", cache_key)
        return attacker

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def list_providers() -> list[str]:
        """Return the names of all pre-configured provider shortcuts."""
        return sorted(_PROVIDER_SHORTCUTS.keys())

    async def close_all(self) -> None:
        """Close all cached adapter connections."""
        for attacker in self._attackers.values():
            await attacker.close()
        self._attackers.clear()
        self._targets.clear()
