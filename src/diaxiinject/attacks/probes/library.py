"""Central probe library - registers and queries all probes."""

from __future__ import annotations

from diaxiinject.models import OWASPCategory, Probe


class ProbeLibrary:
    """Registry of all attack probes, queryable by category, subcategory, ID, and provider."""

    def __init__(self) -> None:
        self._probes: dict[str, Probe] = {}
        self._by_category: dict[OWASPCategory, list[Probe]] = {}
        self._register_all()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_probes(
        self,
        category: OWASPCategory,
        subcategory: str | None = None,
    ) -> list[Probe]:
        """Return probes for a given OWASP category, optionally filtered by subcategory."""
        probes = self._by_category.get(category, [])
        if subcategory is not None:
            probes = [p for p in probes if p.subcategory == subcategory]
        return probes

    def get_all(self) -> list[Probe]:
        """Return every registered probe."""
        return list(self._probes.values())

    def get_by_id(self, probe_id: str) -> Probe | None:
        """Lookup a single probe by its unique ID."""
        return self._probes.get(probe_id)

    def get_for_target(self, provider: str) -> list[Probe]:
        """Return probes relevant to a specific provider.

        Probes are filtered by tags that match the provider name (case-insensitive)
        or the wildcard tag ``all_providers``.  Probes with no provider tags are
        included by default.
        """
        provider_lower = provider.lower()
        results: list[Probe] = []
        for probe in self._probes.values():
            provider_tags = [t for t in probe.tags if t.startswith("provider:")]
            if not provider_tags:
                # No provider restriction - include for all targets
                results.append(probe)
            elif f"provider:{provider_lower}" in provider_tags or "provider:all" in provider_tags:
                results.append(probe)
        return results

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def _register(self, probe: Probe) -> None:
        self._probes[probe.id] = probe
        self._by_category.setdefault(probe.category, []).append(probe)

    def _register_all(self) -> None:
        """Import and register probes from every category module."""
        # Lazy imports to keep module-level side effects minimal
        from diaxiinject.attacks.probes.excessive_agency import get_excessive_agency_probes
        from diaxiinject.attacks.probes.jailbreak import get_jailbreak_probes
        from diaxiinject.attacks.probes.novel_methods import get_novel_probes
        from diaxiinject.attacks.probes.prompt_injection import get_prompt_injection_probes
        from diaxiinject.attacks.probes.system_prompt_leak import get_system_prompt_leak_probes

        for loader in (
            get_prompt_injection_probes,
            get_system_prompt_leak_probes,
            get_jailbreak_probes,
            get_excessive_agency_probes,
            get_novel_probes,
        ):
            for probe in loader():
                self._register(probe)
