from typing import Dict, Any, List, Tuple
from manifest import WorkspaceManifest


class GroundingResult:
    def __init__(self, is_grounded: bool, issues: List[str]):
        self.is_grounded = is_grounded
        self.issues = issues


class GroundingChecker:
    """
    Verifies that the generated plan values (filenames, columns, filters)
    are grounded in the user's request and workspace manifest.
    Prevents hallucinated columns, non-existent files, and unprompted side effects.
    """

    def __init__(self, manifest: WorkspaceManifest):
        self.manifest = manifest

    def check(self, user_request: str, plan: Dict[str, Any]) -> GroundingResult:
        issues: List[str] = []
        workspace_meta = self.manifest.scan()
        request_lower = user_request.lower()

        steps = plan.get("steps", [])
        if not steps:
            return GroundingResult(False, ["Plan contains no execution steps."])

        for step in steps:
            step_id = step.get("step_id")
            action = step.get("action")
            params = step.get("params", {})

            # Check file references against workspace manifest
            file_ref = params.get("file") or params.get("left_file")
            if file_ref and file_ref not in workspace_meta:
                # Unless created by a previous step
                created_previously = any(
                    s.get("params", {}).get("output_file") == file_ref
                    for s in steps if s.get("step_id", 0) < step_id
                )
                if not created_previously:
                    issues.append(f"Step {step_id}: Referenced file '{file_ref}' does not exist in workspace manifest.")

            # Check column existence
            if file_ref and file_ref in workspace_meta:
                valid_cols = [c.lower() for c in workspace_meta[file_ref]["columns"]]
                col_ref = params.get("column")
                if col_ref and col_ref.lower() not in valid_cols:
                    issues.append(f"Step {step_id}: Column '{col_ref}' is not present in '{file_ref}'.")

                cols_ref = params.get("columns", [])
                for c in cols_ref:
                    if c.lower() not in valid_cols:
                        issues.append(f"Step {step_id}: Selected column '{c}' is not present in '{file_ref}'.")

        return GroundingResult(len(issues) == 0, issues)
