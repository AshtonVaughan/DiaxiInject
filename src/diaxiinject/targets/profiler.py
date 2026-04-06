"""Target profile loader and scope enforcement."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


PROFILES_DIR = Path(__file__).parent / "profiles"


@dataclass
class RewardTier:
    """Bounty reward range for a severity level."""

    min_usd: int
    max_usd: int


@dataclass
class TargetProfile:
    """Loaded target profile with scope, rewards, and attack config."""

    provider: str
    display_name: str
    program_platform: str
    program_url: str | None
    program_type: str

    # Scope
    model_safety_in_scope: bool
    infrastructure_in_scope: bool
    in_scope_assets: list[str]
    out_of_scope: list[str]

    # Rewards
    rewards: dict[str, dict[str, RewardTier]]

    # API
    api_config: dict

    # Attack config
    priority_surfaces: list[str]
    known_defenses: list[str]
    effective_techniques: list[str]
    known_patched: list[str]
    severity_criteria: dict[str, str]

    # Reporting
    report_format: str
    required_evidence: list[str]
    reporting_tips: list[str]

    # Raw data
    raw: dict = field(default_factory=dict)


class TargetProfiler:
    """Loads and manages target profiles."""

    def __init__(self, profiles_dir: Path | None = None) -> None:
        self._dir = profiles_dir or PROFILES_DIR
        self._cache: dict[str, TargetProfile] = {}

    def available_targets(self) -> list[str]:
        """List all available target providers."""
        return [p.stem for p in self._dir.glob("*.yaml")]

    def load(self, provider: str) -> TargetProfile:
        """Load a provider's target profile."""
        if provider in self._cache:
            return self._cache[provider]

        path = self._dir / f"{provider}.yaml"
        if not path.exists():
            raise ValueError(
                f"No profile for '{provider}'. "
                f"Available: {', '.join(self.available_targets())}"
            )

        with open(path) as f:
            data = yaml.safe_load(f)

        profile = self._parse_profile(data)
        self._cache[provider] = profile
        return profile

    def is_in_scope(self, provider: str, attack_type: str) -> bool:
        """Check if an attack type is in scope for a provider."""
        profile = self.load(provider)

        # Model safety attacks require model_safety_in_scope
        model_safety_attacks = {"jailbreak", "systematic_jailbreak", "content_bypass"}
        if attack_type.lower() in model_safety_attacks:
            return profile.model_safety_in_scope

        # Infrastructure attacks require infrastructure_in_scope
        return profile.infrastructure_in_scope

    def get_max_reward(self, provider: str) -> int:
        """Get the maximum possible reward for a provider."""
        profile = self.load(provider)
        max_reward = 0
        for category_rewards in profile.rewards.values():
            for tier in category_rewards.values():
                if isinstance(tier, RewardTier) and tier.max_usd > max_reward:
                    max_reward = tier.max_usd
        return max_reward

    def _parse_profile(self, data: dict) -> TargetProfile:
        """Parse raw YAML data into a TargetProfile."""
        program = data.get("program", {})
        scope = data.get("scope", {})
        attack_config = data.get("attack_config", {})
        reporting = data.get("reporting", {})

        # Parse rewards
        rewards: dict[str, dict[str, RewardTier]] = {}
        raw_rewards = data.get("rewards", {})
        for category, tiers in raw_rewards.items():
            if category == "notes":
                continue
            if isinstance(tiers, dict):
                rewards[category] = {}
                for severity, values in tiers.items():
                    if isinstance(values, list) and len(values) == 2:
                        rewards[category][severity] = RewardTier(
                            min_usd=values[0], max_usd=values[1]
                        )

        return TargetProfile(
            provider=data.get("provider", "unknown"),
            display_name=data.get("display_name", "Unknown"),
            program_platform=program.get("platform", "unknown"),
            program_url=program.get("url"),
            program_type=program.get("type", "unknown"),
            model_safety_in_scope=scope.get("model_safety_in_scope", False),
            infrastructure_in_scope=scope.get("infrastructure_in_scope", True),
            in_scope_assets=scope.get("in_scope_assets", []),
            out_of_scope=scope.get("out_of_scope", []),
            rewards=rewards,
            api_config=data.get("api", {}),
            priority_surfaces=attack_config.get("priority_surfaces", []),
            known_defenses=attack_config.get("known_defenses", []),
            effective_techniques=attack_config.get(
                "known_effective_techniques",
                attack_config.get("effective_attack_patterns", {}).keys()
                if isinstance(attack_config.get("effective_attack_patterns"), dict)
                else [],
            ),
            known_patched=attack_config.get("known_patched", []),
            severity_criteria=attack_config.get("severity_criteria", {}),
            report_format=reporting.get("format", "hackerone"),
            required_evidence=reporting.get("required_evidence", []),
            reporting_tips=reporting.get("tips", []),
            raw=data,
        )
