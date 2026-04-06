"""Global configuration for DiaxiInject."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
PROFILES_DIR = Path(__file__).resolve().parent / "targets" / "profiles"
DB_PATH = ROOT_DIR / "db" / "diaxiinject.db"


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
