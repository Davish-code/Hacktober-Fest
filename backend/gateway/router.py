import os
import logging
from typing import Dict, List, Optional
from config import settings
from providers import ProviderAdapter, GeminiAdapter, GroqAdapter, CerebrasAdapter, MockAdapter
from breaker import CircuitBreaker
from governor import Governor

logger = logging.getLogger(__name__)


class GatewayRouter:
    """
    Routes requests based on task role (planner, critic, repairer)
    with automated failover and circuit breaker protection.
    """

    def __init__(self, governor: Optional[Governor] = None, mock_mode: bool = False):
        self.mock_mode = mock_mode
        self.governor = governor or Governor()
        self.breakers: Dict[str, CircuitBreaker] = {}
        self.providers: Dict[str, ProviderAdapter] = {}
        self._init_providers()

    def _init_providers(self):
        if self.mock_mode:
            self.providers["mock"] = MockAdapter()
            self.providers["gemini"] = MockAdapter("gemini-mock")
            self.providers["groq"] = MockAdapter("groq-mock")
        else:
            self.providers["gemini"] = GeminiAdapter()
            self.providers["groq"] = GroqAdapter()
            self.providers["mock"] = MockAdapter()

        for name in self.providers.keys():
            self.breakers[name] = CircuitBreaker(failure_threshold=3, recovery_time=60.0)

    def resolve_provider(self, provider_or_role: str) -> str:
        """
        Resolves provider name or role mapping.
        Enforces Gemini as primary planner and Groq as fallback/critic.
        Bypasses any Cerebras implementations in the routing logic.
        """
        key = provider_or_role.lower().strip()
        critic_choice = getattr(settings, "CRITIC_PROVIDER", "groq").lower().strip()

        # If system requests role 'planner' or 'primary'
        if key in ("planner", "primary"):
            return getattr(settings, "DEFAULT_PLANNER_PROVIDER", "gemini")

        # If system requests CRITIC_PROVIDER or role 'critic' or 'fallback'
        if key in ("critic", "critic_provider", "fallback"):
            return critic_choice

        # Bypass Cerebras implementations in routing logic completely -> routes to Groq
        if key == "cerebras":
            logger.info("Cerebras bypassed in routing logic; defaulting to Groq.")
            return "groq"

        return key

    def get_critic_provider(self) -> ProviderAdapter:
        """Returns the active critic provider adapter (mapped to Groq)."""
        critic_name = self.resolve_provider("critic")
        return self.providers.get(critic_name, self.providers.get("groq"))

    async def execute_with_failover(
        self,
        primary_provider: str,
        fallback_providers: List[str],
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> str:
        resolved_primary = self.resolve_provider(primary_provider)
        resolved_fallbacks = [self.resolve_provider(p) for p in fallback_providers]

        # Deduplicate candidates while preserving order
        seen = set()
        candidates = []
        for p in [resolved_primary] + resolved_fallbacks:
            if p not in seen:
                seen.add(p)
                candidates.append(p)

        for provider_name in candidates:
            if provider_name not in self.providers:
                continue

            breaker = self.breakers.get(provider_name)
            if breaker and not breaker.can_execute():
                logger.warning(f"Circuit open for {provider_name}, skipping to next fallback.")
                continue

            adapter = self.providers[provider_name]
            try:
                self.governor.acquire(provider_name)
                response = await adapter.generate(prompt, system_prompt=system_prompt)
                if breaker:
                    breaker.record_success()
                return response
            except Exception as e:
                logger.error(f"Provider {provider_name} failed: {e}")
                if breaker:
                    breaker.record_failure()

        # If everything fails, try mock provider as safe fallback
        logger.warning("All primary/fallback providers failed, falling back to deterministic mock.")
        return await self.providers["mock"].generate(prompt, system_prompt=system_prompt)
