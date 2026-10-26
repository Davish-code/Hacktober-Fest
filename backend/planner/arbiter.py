from typing import Dict, Any, Tuple, List
from ..core.verifier import PlanVerifier
from ..core.grounding import GroundingChecker


class PlanArbiter:
    """
    Arbitrates between Plan A and Plan B produced by the ensemble.
    Scores plans on:
    - Verifier compliance
    - Grounding against workspace manifest
    - Step efficiency and action consensus
    """

    def __init__(self, verifier: PlanVerifier, grounding_checker: GroundingChecker):
        self.verifier = verifier
        self.grounding = grounding_checker

    def arbitrate(
        self,
        user_request: str,
        plan_a: Dict[str, Any],
        plan_b: Dict[str, Any]
    ) -> Dict[str, Any]:
        score_a, issues_a = self._evaluate_plan(user_request, plan_a)
        score_b, issues_b = self._evaluate_plan(user_request, plan_b)

        # Consensus check: compare actions sequence
        actions_a = [s.get("action") for s in plan_a.get("steps", [])]
        actions_b = [s.get("action") for s in plan_b.get("steps", [])]
        consensus = (actions_a == actions_b and len(actions_a) > 0)

        # Pick highest scoring plan
        if score_a >= score_b and score_a > 0:
            selected = plan_a
            chosen_source = "Planner A"
            chosen_issues = issues_a
        elif score_b > 0:
            selected = plan_b
            chosen_source = "Planner B"
            chosen_issues = issues_b
        else:
            selected = plan_a if len(plan_a.get("steps", [])) > 0 else plan_b
            chosen_source = "Fallback"
            chosen_issues = issues_a + issues_b

        return {
            "selected_plan": selected,
            "chosen_source": chosen_source,
            "consensus": consensus,
            "score_a": score_a,
            "score_b": score_b,
            "validation_issues": chosen_issues
        }

    def _evaluate_plan(self, user_request: str, plan: Dict[str, Any]) -> Tuple[float, List[str]]:
        if not plan or not plan.get("steps"):
            return 0.0, ["Empty plan"]

        score = 100.0
        issues = []

        # 1. Structural verification
        ver_res = self.verifier.verify(plan)
        if not ver_res.is_valid:
            score -= 50.0
            issues.extend(ver_res.errors)

        # 2. Grounding check
        grd_res = self.grounding.check(user_request, plan)
        if not grd_res.is_grounded:
            score -= 30.0
            issues.extend(grd_res.issues)

        # 3. Penalize redundant step count
        step_count = len(plan.get("steps", []))
        if step_count > 10:
            score -= 10.0

        return max(score, 0.0), issues
