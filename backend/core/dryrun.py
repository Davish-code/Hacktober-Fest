from typing import Dict, Any, List
from pathlib import Path
from registry import ActionRegistry, ActionEffect
from manifest import WorkspaceManifest


class DryRunResult:
    def __init__(self, success: bool, steps_simulated: List[Dict[str, Any]], error: str = ""):
        self.success = success
        self.steps_simulated = steps_simulated
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "error": self.error,
            "steps": self.steps_simulated
        }


class DryRunSimulator:
    """
    Simulates plan execution completely in-memory with zero side effects.
    Validates state transitions, predicts input/output artifacts,
    and identifies runtime failures prior to persistent execution.
    """

    def __init__(self, workspace_path: Path):
        self.workspace_path = Path(workspace_path)
        self.manifest = WorkspaceManifest(self.workspace_path)

    def simulate(self, plan: Dict[str, Any]) -> DryRunResult:
        steps = plan.get("steps", [])
        simulated_artifacts = set(self.manifest.scan().keys())
        simulation_log = []

        for step in steps:
            step_id = step.get("step_id")
            action = step.get("action")
            params = step.get("params", {})
            action_def = ActionRegistry.get_action(action)

            # Check read inputs
            file_ref = params.get("file") or params.get("left_file")
            if file_ref and file_ref not in simulated_artifacts:
                return DryRunResult(
                    success=False,
                    steps_simulated=simulation_log,
                    error=f"Simulation failed at Step {step_id}: Input file '{file_ref}' not found in state."
                )

            # Predict generated outputs
            output_file = params.get("output_file")
            if output_file:
                simulated_artifacts.add(output_file)

            if action in ("join_rows", "JOIN_ROWS"):
                predicted = "joined rows in memory"
            elif action in ("aggregate",) or (action == "AGGREGATE" and "rows" in params):
                predicted = "aggregated rows in memory"
            else:
                predicted = output_file or "in-memory intermediate state"

            simulation_log.append({
                "step_id": step_id,
                "action": action,
                "effect": action_def.effect.value,
                "status": "SIMULATED_SUCCESS",
                "predicted_output": predicted
            })

        return DryRunResult(success=True, steps_simulated=simulation_log)
