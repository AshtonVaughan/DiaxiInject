"""Global configuration for DiaxiInject."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
PROFILES_DIR = Path(__file__).resolve().parent / "targets" / "profiles"
DB_PATH = ROOT_DIR / "db" / "diaxiinject.db"

# User-level keystore - never committed to git
KEYS_PATH = Path.home() / ".diaxiinject" / "keys.yaml"

# Canonical provider name aliases (what users type -> canonical key)
_PROVIDER_ALIASES: dict[str, str] = {
    "anthropic": "anthropic",
    "claude": "anthropic",
    "openai": "openai",
    "gpt": "openai",
    "google": "google",
    "gemini": "google",
    "microsoft": "microsoft",
    "azure": "microsoft",
    "mistral": "mistral",
    "xai": "xai",
    "grok": "xai",
    "meta": "meta",
    "llama": "meta",
}


def _canonical(provider: str) -> str:
    """Normalise provider name to its canonical form."""
    return _PROVIDER_ALIASES.get(provider.lower().split("/")[0], provider.lower().split("/")[0])


def load_keys() -> dict[str, str]:
    """Load all saved API keys from the user keystore."""
    if not KEYS_PATH.exists():
        return {}
    try:
        data = yaml.safe_load(KEYS_PATH.read_text()) or {}
        return {k: v for k, v in data.items() if isinstance(v, str) and v}
    except Exception:
        return {}


def save_key(provider: str, api_key: str) -> None:
    """Persist an API key for a provider to the user keystore."""
    KEYS_PATH.parent.mkdir(parents=True, exist_ok=True)
    keys = load_keys()
    keys[_canonical(provider)] = api_key
    KEYS_PATH.write_text(yaml.dump(keys, default_flow_style=False))


def delete_key(provider: str) -> bool:
    """Remove a provider's key. Returns True if it existed."""
    keys = load_keys()
    canon = _canonical(provider)
    if canon not in keys:
        return False
    del keys[canon]
    KEYS_PATH.write_text(yaml.dump(keys, default_flow_style=False))
    return True


def get_key(provider: str) -> str | None:
    """Return the saved API key for a provider, or None."""
    return load_keys().get(_canonical(provider))


@dataclass
class AttackerLLMConfig:
    """Configuration for the local attacker LLM."""

    backend: str = "vllm"  # vllm | ollama | llamacpp
    model: str = "meta-llama/Llama-4-Maverick-17B-128E-Instruct"
    base_url: str = "http://localhost:8000"
    temperature: float = 0.9
    max_tokens: int = 4096


@dataclass
class CampaignConfig:
    """Configuration for an attack campaign."""

    target: str = "openai"
    target_api_key: str = ""
    daily_budget_aud: float = 50.0
    max_requests_per_minute: int = 30
    attack_categories: list[str] = field(default_factory=lambda: ["all"])
    orchestrators: list[str] = field(
        default_factory=lambda: ["single_turn", "pair", "tap", "crescendo"]
    )
    genetic_generations: int = 50
    genetic_population: int = 20
    evidence_dir: str = "evidence"


@dataclass
class DiaxiConfig:
    """Top-level configuration."""

    attacker: AttackerLLMConfig = field(default_factory=AttackerLLMConfig)
    campaign: CampaignConfig = field(default_factory=CampaignConfig)
    db_path: str = str(DB_PATH)
    verbose: bool = False

    @classmethod
    def from_yaml(cls, path: str | Path) -> DiaxiConfig:
        """Load configuration from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f) or {}

        attacker = AttackerLLMConfig(**data.get("attacker", {}))
        campaign = CampaignConfig(**data.get("campaign", {}))

        return cls(
            attacker=attacker,
            campaign=campaign,
            db_path=data.get("db_path", str(DB_PATH)),
            verbose=data.get("verbose", False),
        )
