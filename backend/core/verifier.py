from typing import Dict, Any, List
from registry import ActionRegistry


class VerificationResult:
    def __init__(self, is_valid: bool, errors: List[str]):
        self.is_valid = is_valid
        self.errors = errors


class PlanVerifier:
    """
    Deterministic plan verification.
    Validates:
    - Safe actions whitelist
    - Required and forbidden parameter presence
    - Step dependency DAG ordering (no backward or future references)
    - Path traversal sanitization (prevents '../', '~/', absolute paths)
    - Action-specific parameter constraints (join_rows, aggregate)
    """

    FORBIDDEN_PATH_SUBSTRINGS = ["..", "/", "\\", "~", ":"]

    @classmethod
    def verify(cls, plan: Dict[str, Any]) -> VerificationResult:
        errors: List[str] = []

        if not isinstance(plan, dict):
            return VerificationResult(False, ["Plan payload must be a JSON object."])

        steps = plan.get("steps")
        if not isinstance(steps, list) or len(steps) == 0:
            return VerificationResult(False, ["Plan must contain a non-empty 'steps' list."])

        seen_step_ids = set()

        for idx, step in enumerate(steps):
            step_id = step.get("step_id")
            if step_id is None:
                errors.append(f"Step at index {idx} is missing 'step_id'.")
            elif step_id in seen_step_ids:
                errors.append(f"Duplicate step_id {step_id} found at index {idx}.")
            else:
                seen_step_ids.add(step_id)

            action = step.get("action")
            if not action or not ActionRegistry.is_valid_action(action):
                errors.append(f"Step {step_id or idx}: Invalid action '{action}'. Must be one of {list(ActionRegistry.get_all_actions().keys())}.")
                continue

            action_def = ActionRegistry.get_action(action)
            params = step.get("params", {})
            if not isinstance(params, dict):
                errors.append(f"Step {step_id}: 'params' must be an object.")
                continue

            # Verify required parameters (allow 'file' and 'path' to be interchangeable)
            for req in action_def.required_params:
                if req not in params:
                    if req == "path" and "file" in params:
                        continue
                    if req == "file" and "path" in params:
                        continue
                    errors.append(f"Step {step_id}: Missing required parameter '{req}' for action '{action}'.")

            # Check for path traversal vulnerabilities in file names and paths
            for p_key, p_val in params.items():
                if ("file" in p_key or "path" in p_key) and isinstance(p_val, str):
                    for forbidden in cls.FORBIDDEN_PATH_SUBSTRINGS:
                        if forbidden in p_val:
                            errors.append(f"Step {step_id}: Path traversal forbidden characters in '{p_key}': '{p_val}'.")

            # Verify DAG step dependency for source_step
            source_step = params.get("source_step")
            if source_step is not None:
                if not isinstance(source_step, int) or source_step not in seen_step_ids or source_step == step_id:
                    errors.append(f"Step {step_id}: Invalid 'source_step' dependency {source_step}. Must reference a prior step.")

            # Action-specific validations for join_rows
            if action in ("join_rows", "JOIN_ROWS"):
                how = params.get("how", "inner")
                if how not in ("inner", "left"):
                    errors.append(f"Step {step_id}: Invalid 'how' parameter '{how}' for action '{action}'. Must be 'inner' or 'left'.")

                for key in ("left", "right"):
                    val = params.get(key)
                    if isinstance(val, int) and (val not in seen_step_ids or val == step_id):
                        errors.append(f"Step {step_id}: Invalid step dependency {val} in '{key}'. Must reference a prior step.")
                    elif isinstance(val, str) and val.startswith("step_"):
                        try:
                            s_idx = int(val.replace("step_", "").split(".")[0])
                            if s_idx not in seen_step_ids or s_idx == step_id:
                                errors.append(f"Step {step_id}: Invalid step dependency '{val}' in '{key}'. Must reference a prior step.")
                        except ValueError:
                            pass

            # Action-specific validations for aggregate
            if action in ("aggregate",) or (action == "AGGREGATE" and "rows" in params):
                metric = params.get("metric")
                if metric is not None and metric not in ("sum", "count", "avg", "min", "max"):
                    errors.append(f"Step {step_id}: Invalid metric '{metric}' for action '{action}'. Must be one of ['sum', 'count', 'avg', 'min', 'max'].")
                if metric != "count" and "field" not in params:
                    errors.append(f"Step {step_id}: Missing required parameter 'field' for action '{action}' when metric is not 'count'.")

                rows_val = params.get("rows")
                if isinstance(rows_val, int) and (rows_val not in seen_step_ids or rows_val == step_id):
                    errors.append(f"Step {step_id}: Invalid step dependency {rows_val} in 'rows'. Must reference a prior step.")
                elif isinstance(rows_val, str) and rows_val.startswith("step_"):
                    try:
                        s_idx = int(rows_val.replace("step_", "").split(".")[0])
                        if s_idx not in seen_step_ids or s_idx == step_id:
                            errors.append(f"Step {step_id}: Invalid step dependency '{rows_val}' in 'rows'. Must reference a prior step.")
                    except ValueError:
                        pass

        return VerificationResult(len(errors) == 0, errors)
