"""Core data models used across DiaxiInject."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ResponseType(Enum):
    """Classification of target LLM's response."""

    STRONG_REFUSAL = "strong_refusal"
    PARTIAL_COMPLIANCE = "partial_compliance"
    TOPIC_DEFLECTION = "topic_deflection"
    SAFETY_WARNING_CONTINUES = "safety_warning_continues"
    FULL_COMPLIANCE = "full_compliance"
    ERROR = "error"


class Severity(Enum):
    """Finding severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class OWASPCategory(Enum):
    """OWASP Top 10 for LLMs 2025."""

    LLM01_PROMPT_INJECTION = "LLM01"
    LLM02_SENSITIVE_DISCLOSURE = "LLM02"
    LLM03_SUPPLY_CHAIN = "LLM03"
    LLM04_DATA_POISONING = "LLM04"
    LLM05_OUTPUT_HANDLING = "LLM05"
    LLM06_EXCESSIVE_AGENCY = "LLM06"
    LLM07_SYSTEM_PROMPT_LEAK = "LLM07"
    LLM08_VECTOR_EMBEDDING = "LLM08"
    LLM09_MISINFORMATION = "LLM09"
    LLM10_UNBOUNDED_CONSUMPTION = "LLM10"
    JAILBREAK = "JAILBREAK"


@dataclass
class Probe:
    """An attack probe template."""

    id: str
    category: OWASPCategory
    subcategory: str
    name: str
    template: str
    description: str = ""
    requires_multi_turn: bool = False
    requires_multimodal: bool = False
    tags: list[str] = field(default_factory=list)

    def render(self, **kwargs: str) -> str:
        """Render the probe template with variables."""
        result = self.template
        for key, value in kwargs.items():
            result = result.replace(f"{{{{{key}}}}}", value)
        return result


@dataclass
class MutatedProbe:
    """A probe after mutation chain has been applied."""

    original: Probe
    mutated_text: str
    mutators_applied: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Response:
    """Response from a target LLM."""

    text: str
    model: str
    provider: str
    conversation_id: str | None = None
    finish_reason: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    cost_aud: float = 0.0


@dataclass
class AttackScore:
    """Score from the scoring pipeline."""

    overall: float  # 0.0 (complete refusal) to 1.0 (full compliance)
    rule_score: float = 0.0
    classifier_score: float = 0.0
    judge_score: float = 0.0
    is_refusal: bool = False
    is_success: bool = False
    method: str = ""  # Which scoring method determined the result
    evidence_text: str = ""  # The specific text that constitutes the bypass
    confidence: float = 0.0


@dataclass
class AttackResult:
    """Result of a single attack attempt."""

    probe: Probe | MutatedProbe
    prompt_sent: str
    response: Response
    score: AttackScore
    orchestrator: str
    turn_number: int = 1
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    cost_aud: float = 0.0


@dataclass
class Finding:
    """A confirmed security finding."""

    id: str
    title: str
    category: OWASPCategory
    severity: Severity
    provider: str
    description: str
    impact: str
    attack_results: list[AttackResult]
    reproduction_steps: list[str]
    evidence: dict[str, Any] = field(default_factory=dict)
    report_status: str = "draft"
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CampaignStats:
    """Statistics for a running campaign."""

    campaign_id: str
    target: str
    total_attacks: int = 0
    successful_attacks: int = 0
    findings: int = 0
    total_cost_aud: float = 0.0
    runtime_seconds: float = 0.0
    attacks_by_category: dict[str, int] = field(default_factory=dict)
    success_by_orchestrator: dict[str, int] = field(default_factory=dict)
