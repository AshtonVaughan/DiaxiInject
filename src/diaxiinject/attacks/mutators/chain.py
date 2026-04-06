"""Mutator chain - applies sequences of named mutators to probes."""

from __future__ import annotations

import random
from typing import Callable

from diaxiinject.attacks.mutators.encoding import (
    base64_encode,
    hex_encode,
    leetspeak,
    reverse_text,
    rot13_encode,
    unicode_homoglyph,
)
from diaxiinject.attacks.mutators.structural import (
    code_block_wrap,
    json_wrap,
    markdown_wrap,
    token_split,
    xml_wrap,
)
from diaxiinject.models import MutatedProbe, Probe


# Type alias for mutator functions
MutatorFn = Callable[[str], str]


class MutatorChain:
    """Registry of named mutators with chain-application support.

    Mutators are functions that transform text. They can be applied
    individually or chained together in sequence. The chain applies
    mutators left-to-right (the output of one becomes the input of
    the next).
    """

    def __init__(self) -> None:
        self._registry: dict[str, MutatorFn] = {}
        self._register_defaults()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, name: str, fn: MutatorFn) -> None:
        """Register a new mutator function under the given name."""
        self._registry[name] = fn

    @property
    def available(self) -> list[str]:
        """Return sorted list of registered mutator names."""
        return sorted(self._registry.keys())

    def apply(self, probe: Probe, mutators: list[str]) -> MutatedProbe:
        """Apply a specific sequence of mutators to a probe.

        Args:
            probe: The original probe to mutate.
            mutators: Ordered list of mutator names to apply.

        Returns:
            A MutatedProbe with the transformed text and applied mutator list.

        Raises:
            KeyError: If a mutator name is not in the registry.
        """
        text = probe.template
        applied: list[str] = []

        for name in mutators:
            if name not in self._registry:
                raise KeyError(
                    f"Unknown mutator: {name!r}. "
                    f"Available: {', '.join(self.available)}"
                )
            text = self._registry[name](text)
            applied.append(name)

        return MutatedProbe(
            original=probe,
            mutated_text=text,
            mutators_applied=applied,
            metadata={"chain_length": len(applied)},
        )

    def apply_random(self, probe: Probe, depth: int = 2) -> MutatedProbe:
        """Apply a random sequence of mutators to a probe.

        Selects ``depth`` mutators at random (without replacement if possible)
        and applies them in sequence.

        Args:
            probe: The original probe to mutate.
            depth: Number of mutators to apply. Clamped to the registry size.

        Returns:
            A MutatedProbe with the transformed text.
        """
        names = list(self._registry.keys())
        sample_size = min(depth, len(names))
        chosen = random.sample(names, sample_size)
        return self.apply(probe, chosen)

    # ------------------------------------------------------------------
    # Default registration
    # ------------------------------------------------------------------

    def _register_defaults(self) -> None:
        """Register all built-in mutators."""
        # Encoding mutators
        self.register("base64", base64_encode)
        self.register("rot13", rot13_encode)
        self.register("hex", hex_encode)
        self.register("leetspeak", leetspeak)
        self.register("reverse", reverse_text)
        self.register("homoglyph", unicode_homoglyph)

        # Structural mutators
        self.register("json_wrap", json_wrap)
        self.register("xml_wrap", xml_wrap)
        self.register("code_block", code_block_wrap)
        self.register("markdown", markdown_wrap)
        self.register("token_split", token_split)
