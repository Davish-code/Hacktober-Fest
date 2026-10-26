import asyncio
import json
import logging
from typing import Dict, Any, Tuple
from ..config import settings
from ..gateway.router import GatewayRouter
from .prompts import PLANNER_SYSTEM_PROMPT, format_planner_prompt

logger = logging.getLogger(__name__)


class PlannerEnsemble:
    """
    Executes Planner A and Planner B concurrently using different LLM providers or strategies
    to increase plan reliability and eliminate single-model biases.
    """

    def __init__(self, router: GatewayRouter):
        self.router = router

    async def generate_dual_plans(
        self,
        user_request: str,
        manifest: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        prompt = format_planner_prompt(user_request, manifest)

        critic_prov = getattr(settings, "CRITIC_PROVIDER", "groq")
        planner_a = getattr(settings, "DEFAULT_PLANNER_PROVIDER", "gemini")
        planner_b = getattr(settings, "FALLBACK_PLANNER_PROVIDER", "groq")

        # Run Planner A (primary: gemini) and Planner B (secondary: groq) in parallel
        task_a = self.router.execute_with_failover(
            primary_provider=planner_a,
            fallback_providers=[planner_b, critic_prov],
            prompt=prompt,
            system_prompt=PLANNER_SYSTEM_PROMPT
        )
        task_b = self.router.execute_with_failover(
            primary_provider=planner_b,
            fallback_providers=[critic_prov, planner_a],
            prompt=prompt,
            system_prompt=PLANNER_SYSTEM_PROMPT
        )

        raw_a, raw_b = await asyncio.gather(task_a, task_b, return_exceptions=True)

        plan_a = self._parse_json(raw_a)
        plan_b = self._parse_json(raw_b)

        return plan_a, plan_b

    def _parse_json(self, raw_output: Any) -> Dict[str, Any]:
        if isinstance(raw_output, Exception):
            logger.error(f"Planner failed with exception: {raw_output}")
            return {"intent": "error", "steps": []}
        try:
            # Strip markdown code blocks if model included them
            text = str(raw_output).strip()
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            return json.loads(text.strip())
        except Exception as e:
            logger.warning(f"Failed to parse planner JSON: {e}")
            return {"intent": "failed_parse", "steps": []}
