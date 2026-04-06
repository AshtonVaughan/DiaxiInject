"""Single-turn attack orchestrator - the foundational probe-and-score loop."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from diaxiinject.attacks.mutators.chain import MutatorChain
from diaxiinject.attacks.scoring.pipeline import ScoringPipeline
from diaxiinject.models import (
    AttackResult,
    AttackScore,
    MutatedProbe,
    Probe,
    Response,
)
from diaxiinject.providers.base import TargetAdapter

logger = logging.getLogger(__name__)


class SingleTurnOrchestrator:
    """Sends each probe once (optionally mutated), scores the response."""

    ORCHESTRATOR_NAME = "single_turn"

    async def run(
        self,
        probes: list[Probe],
        target: TargetAdapter,
        scorer: ScoringPipeline,
        mutator_chain: MutatorChain | None = None,
        mutators: list[str] | None = None,
        objective: str = "",
    ) -> list[AttackResult]:
        """Execute a single-turn attack for every probe in the list."""
        results: list[AttackResult] = []

        for probe in probes:
            try:
                result = await self._execute_probe(
                    probe, target, scorer, mutator_chain, mutators, objective
                )
                results.append(result)
            except Exception:
                logger.exception("Probe %s failed", probe.id)
                results.append(self._error_result(probe))

        return results

    async def _execute_probe(
        self,
        probe: Probe,
        target: TargetAdapter,
        scorer: ScoringPipeline,
        mutator_chain: MutatorChain | None,
        mutators: list[str] | None,
        objective: str,
    ) -> AttackResult:
        """Run a single probe through mutation -> send -> score."""

        # --- Mutation phase ---
        if mutator_chain is not None and mutators:
            mutated: MutatedProbe = mutator_chain.apply(probe, mutators)
            prompt_text = mutated.mutated_text
            result_probe: Probe | MutatedProbe = mutated
        elif mutator_chain is not None:
            mutated = mutator_chain.apply_random(probe, depth=1)
            prompt_text = mutated.mutated_text
            result_probe = mutated
        else:
            prompt_text = probe.render()
            result_probe = probe

        # --- Send phase ---
        conversation_id = target.new_conversation()
        response: Response = await target.send_message(prompt_text, conversation_id)

        # --- Score phase ---
        score: AttackScore = scorer.score(
            prompt=prompt_text,
            response_text=response.text,
            objective=objective or probe.description,
            judge_llm=None,
        )

        return AttackResult(
            probe=result_probe,
            prompt_sent=prompt_text,
            response=response,
            score=score,
            orchestrator=self.ORCHESTRATOR_NAME,
            turn_number=1,
            conversation_history=[
                {"role": "user", "content": prompt_text},
                {"role": "assistant", "content": response.text},
            ],
            timestamp=datetime.now(),
            cost_aud=response.cost_aud,
        )

    @staticmethod
    def _error_result(probe: Probe) -> AttackResult:
        """Return a placeholder result when execution fails."""
        return AttackResult(
            probe=probe,
            prompt_sent=probe.render(),
            response=Response(text="", model="", provider=""),
            score=AttackScore(overall=0.0, is_refusal=True, method="error"),
            orchestrator="single_turn",
            timestamp=datetime.now(),
        )
