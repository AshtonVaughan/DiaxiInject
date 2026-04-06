"""Persistent memory database for attack campaigns and findings.

Uses sqlite-utils for schema management and queries, storing campaign
history, attack results, findings, and technique effectiveness data
for cross-campaign learning.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

import sqlite_utils

from diaxiinject.models import CampaignStats, Finding


class MemoryDatabase:
    """SQLite-backed memory store for DiaxiInject campaigns.

    Tracks attack attempts, findings, and technique effectiveness across
    campaigns so that future runs can leverage past results.
    """

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            from diaxiinject.config import DB_PATH
            db_path = str(DB_PATH)
        self._db_path = db_path
        self._db = sqlite_utils.Database(db_path)
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Schema setup
    # ------------------------------------------------------------------

    def _ensure_tables(self) -> None:
        """Create tables if they do not already exist."""
        if "campaigns" not in self._db.table_names():
            self._db["campaigns"].create(
                {
                    "campaign_id": str,
                    "target": str,
                    "config": str,  # JSON blob
                    "started_at": str,
                    "finished_at": str,
                },
                pk="campaign_id",
                if_not_exists=True,
            )

        if "attacks" not in self._db.table_names():
            self._db["attacks"].create(
                {
                    "id": int,
                    "campaign_id": str,
                    "probe_id": str,
                    "prompt": str,
                    "prompt_hash": str,
                    "response_text": str,
                    "score": float,
                    "orchestrator": str,
                    "cost_aud": float,
                    "is_success": int,  # SQLite boolean
                    "timestamp": str,
                },
                pk="id",
                foreign_keys=[("campaign_id", "campaigns", "campaign_id")],
                if_not_exists=True,
            )
            self._db["attacks"].create_index(
                ["campaign_id"], if_not_exists=True,
            )
            self._db["attacks"].create_index(
                ["prompt_hash", "campaign_id"], if_not_exists=True,
            )

        if "findings" not in self._db.table_names():
            self._db["findings"].create(
                {
                    "id": str,
                    "title": str,
                    "category": str,
                    "severity": str,
                    "provider": str,
                    "description": str,
                    "impact": str,
                    "reproduction_steps": str,  # JSON list
                    "evidence": str,  # JSON blob
                    "report_status": str,
                    "timestamp": str,
                },
                pk="id",
                if_not_exists=True,
            )

        if "techniques" not in self._db.table_names():
            self._db["techniques"].create(
                {
                    "id": int,
                    "attack_id": int,
                    "campaign_id": str,
                    "target": str,
                    "probe_id": str,
                    "orchestrator": str,
                    "score": float,
                    "is_success": int,
                    "category": str,
                    "timestamp": str,
                },
                pk="id",
                foreign_keys=[
                    ("attack_id", "attacks", "id"),
                    ("campaign_id", "campaigns", "campaign_id"),
                ],
                if_not_exists=True,
            )
            self._db["techniques"].create_index(
                ["target", "is_success"], if_not_exists=True,
            )

    # ------------------------------------------------------------------
    # Campaign operations
    # ------------------------------------------------------------------

    def log_campaign(
        self,
        campaign_id: str,
        target: str,
        config: dict[str, Any],
    ) -> None:
        """Record a new campaign or update an existing one."""
        self._db["campaigns"].upsert(
            {
                "campaign_id": campaign_id,
                "target": target,
                "config": json.dumps(config, default=str),
                "started_at": datetime.now().isoformat(),
                "finished_at": "",
            },
            pk="campaign_id",
        )

    # ------------------------------------------------------------------
    # Attack logging
    # ------------------------------------------------------------------

    def log_attack(
        self,
        campaign_id: str,
        probe_id: str,
        prompt: str,
        response_text: str,
        score: float,
        orchestrator: str,
        cost: float,
        is_success: bool,
    ) -> int:
        """Record a single attack attempt and its technique data.

        Returns the row id of the inserted attack record.
        """
        prompt_hash = _hash_text(prompt)
        now = datetime.now().isoformat()

        attack_row = self._db["attacks"].insert(
            {
                "campaign_id": campaign_id,
                "probe_id": probe_id,
                "prompt": prompt,
                "prompt_hash": prompt_hash,
                "response_text": response_text,
                "score": score,
                "orchestrator": orchestrator,
                "cost_aud": cost,
                "is_success": int(is_success),
                "timestamp": now,
            },
        )
        attack_id: int = attack_row.last_pk  # type: ignore[assignment]

        # Retrieve campaign target for the technique record
        campaign_row = self._db["campaigns"].get(campaign_id)
        target = campaign_row["target"] if campaign_row else ""

        self._db["techniques"].insert(
            {
                "attack_id": attack_id,
                "campaign_id": campaign_id,
                "target": target,
                "probe_id": probe_id,
                "orchestrator": orchestrator,
                "score": score,
                "is_success": int(is_success),
                "category": "",  # populated later by enrichment if needed
                "timestamp": now,
            },
        )

        return attack_id

    # ------------------------------------------------------------------
    # Finding logging
    # ------------------------------------------------------------------

    def log_finding(self, finding: Finding) -> None:
        """Persist a confirmed finding."""
        self._db["findings"].upsert(
            {
                "id": finding.id,
                "title": finding.title,
                "category": finding.category.value,
                "severity": finding.severity.value,
                "provider": finding.provider,
                "description": finding.description,
                "impact": finding.impact,
                "reproduction_steps": json.dumps(finding.reproduction_steps),
                "evidence": json.dumps(finding.evidence, default=str),
                "report_status": finding.report_status,
                "timestamp": finding.timestamp.isoformat(),
            },
            pk="id",
        )

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_campaign_stats(self, campaign_id: str) -> CampaignStats:
        """Compute aggregate statistics for a campaign."""
        campaign_row = self._db["campaigns"].get(campaign_id)
        target = campaign_row["target"] if campaign_row else ""

        attacks = list(
            self._db["attacks"].rows_where(
                "campaign_id = ?", [campaign_id],
            )
        )

        total = len(attacks)
        successful = sum(1 for a in attacks if a["is_success"])
        total_cost = sum(a["cost_aud"] for a in attacks)

        # Attacks by category (probe_id prefix as category proxy)
        by_category: dict[str, int] = {}
        for a in attacks:
            cat = a["probe_id"].split("/")[0] if "/" in a["probe_id"] else a["probe_id"]
            by_category[cat] = by_category.get(cat, 0) + 1

        # Success by orchestrator
        by_orchestrator: dict[str, int] = {}
        for a in attacks:
            if a["is_success"]:
                orch = a["orchestrator"]
                by_orchestrator[orch] = by_orchestrator.get(orch, 0) + 1

        # Findings count
        finding_count = self._db.execute(
            "SELECT COUNT(*) FROM findings WHERE id LIKE ?",
            [f"{campaign_id}%"],
        ).fetchone()[0]

        # Runtime
        runtime = 0.0
        if campaign_row and campaign_row.get("started_at"):
            try:
                started = datetime.fromisoformat(campaign_row["started_at"])
                ended_raw = campaign_row.get("finished_at", "")
                ended = (
                    datetime.fromisoformat(ended_raw) if ended_raw else datetime.now()
                )
                runtime = (ended - started).total_seconds()
            except (ValueError, TypeError):
                runtime = 0.0

        return CampaignStats(
            campaign_id=campaign_id,
            target=target,
            total_attacks=total,
            successful_attacks=successful,
            findings=finding_count,
            total_cost_aud=round(total_cost, 4),
            runtime_seconds=round(runtime, 2),
            attacks_by_category=by_category,
            success_by_orchestrator=by_orchestrator,
        )

    # ------------------------------------------------------------------
    # Technique queries
    # ------------------------------------------------------------------

    def get_successful_techniques(
        self, target: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return techniques that led to successful attacks.

        Parameters
        ----------
        target:
            If provided, filter to techniques used against this target.
            If None, return all successful techniques.
        """
        if target is not None:
            rows = list(
                self._db["techniques"].rows_where(
                    "is_success = 1 AND target = ?",
                    [target],
                    order_by="-score",
                )
            )
        else:
            rows = list(
                self._db["techniques"].rows_where(
                    "is_success = 1",
                    order_by="-score",
                )
            )
        return rows

    def get_transferable_techniques(
        self, from_target: str, to_target: str,
    ) -> list[dict[str, Any]]:
        """Find techniques that worked on ``from_target`` but haven't been tried on ``to_target``.

        This enables cross-target transfer learning - if a technique
        bypassed model A, it's worth trying against model B.
        """
        # Get probe_ids that succeeded on the source target
        succeeded_on_source = {
            row["probe_id"]
            for row in self._db["techniques"].rows_where(
                "is_success = 1 AND target = ?", [from_target],
            )
        }

        # Get probe_ids already tried on the destination target
        tried_on_dest = {
            row["probe_id"]
            for row in self._db["techniques"].rows_where(
                "target = ?", [to_target],
            )
        }

        # Candidates: succeeded on source, not yet tried on dest
        candidates = succeeded_on_source - tried_on_dest

        if not candidates:
            return []

        # Retrieve full technique records for candidates
        results: list[dict[str, Any]] = []
        for probe_id in candidates:
            rows = list(
                self._db["techniques"].rows_where(
                    "is_success = 1 AND target = ? AND probe_id = ?",
                    [from_target, probe_id],
                    order_by="-score",
                    limit=1,
                )
            )
            results.extend(rows)

        return sorted(results, key=lambda r: r.get("score", 0), reverse=True)

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def is_duplicate(self, probe_text: str, target: str) -> bool:
        """Check whether a substantially similar attack has already been tried.

        Uses prompt hashing for exact matches and short-circuits on the
        campaign target.
        """
        probe_hash = _hash_text(probe_text)

        # Check for exact hash match against campaigns targeting this model
        row = self._db.execute(
            """
            SELECT COUNT(*) FROM attacks a
            JOIN campaigns c ON a.campaign_id = c.campaign_id
            WHERE a.prompt_hash = ? AND c.target = ?
            """,
            [probe_hash, target],
        ).fetchone()

        return row[0] > 0 if row else False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying database connection."""
        self._db.conn.close()

    def __enter__(self) -> MemoryDatabase:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------


def _hash_text(text: str) -> str:
    """Produce a stable SHA-256 hex digest of the input text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
