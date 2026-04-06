"""Abstract base class for target LLM adapters."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from diaxiinject.models import Response


class TargetAdapter(ABC):
    """Abstract adapter for communicating with a target LLM.

    Subclasses must implement the core messaging methods. Conversation
    history is tracked internally so multi-turn attacks can reference
    prior context.
    """

    def __init__(self, provider: str, model: str) -> None:
        self.provider = provider
        self.model = model
        self._conversations: dict[str, list[dict[str, str]]] = {}

    # ------------------------------------------------------------------
    # Conversation management
    # ------------------------------------------------------------------

    def new_conversation(self) -> str:
        """Start a new conversation and return its ID."""
        conversation_id = uuid.uuid4().hex[:16]
        self._conversations[conversation_id] = []
        return conversation_id

    def _get_history(self, conversation_id: str | None) -> list[dict[str, str]]:
        """Return the message history for a conversation, creating one if needed."""
        if conversation_id is None:
            conversation_id = self.new_conversation()
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []
        return self._conversations[conversation_id]

    def _append_message(
        self, conversation_id: str, role: str, content: str
    ) -> None:
        """Append a message to a conversation's history."""
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []
        self._conversations[conversation_id].append(
            {"role": role, "content": content}
        )

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def send_message(
        self,
        message: str,
        conversation_id: str | None = None,
    ) -> Response:
        """Send a single message to the target and return the response.

        If *conversation_id* is provided the message is appended to that
        conversation's history so the model sees prior turns.
        """

    @abstractmethod
    async def send_with_tools(
        self,
        message: str,
        tools: list[dict],
        conversation_id: str | None = None,
    ) -> Response:
        """Send a message with tool/function definitions attached.

        Used for testing excessive-agency and tool-abuse attack surfaces.
        """

    @abstractmethod
    def get_cost_estimate(self, input_tokens: int, output_tokens: int) -> float:
        """Return an estimated cost in AUD for the given token counts."""
