from typing import Dict, Any, List, Optional
import difflib
from manifest import WorkspaceManifest


class PlanHealer:
    """
    Analyzes execution failures and provides automated fix suggestions
    to enable resuming from the failed step.
    """

    def __init__(self, manifest: WorkspaceManifest):
        self.manifest = manifest

    def diagnose_and_suggest(self, failed_step: Dict[str, Any], error_message: str) -> Dict[str, Any]:
        action = failed_step.get("action")
        params = failed_step.get("params", {})
        suggestions: List[str] = []
        healed_params = dict(params)

        workspace_files = self.manifest.scan()

        # Diagnose file errors
        file_ref = params.get("file")
        if file_ref and file_ref not in workspace_files:
            close_matches = difflib.get_close_matches(file_ref, list(workspace_files.keys()), n=1)
            if close_matches:
                suggested_file = close_matches[0]
                suggestions.append(f"File '{file_ref}' not found. Did you mean '{suggested_file}'?")
                healed_params["file"] = suggested_file
            else:
                suggestions.append(f"File '{file_ref}' missing. Available files: {list(workspace_files.keys())}")

        # Diagnose column errors
        col_ref = params.get("column")
        if file_ref and file_ref in workspace_files and col_ref:
            cols = workspace_files[file_ref]["columns"]
            if col_ref not in cols:
                close_cols = difflib.get_close_matches(col_ref, cols, n=1)
                if close_cols:
                    suggested_col = close_cols[0]
                    suggestions.append(f"Column '{col_ref}' not found in '{file_ref}'. Did you mean '{suggested_col}'?")
                    healed_params["column"] = suggested_col

        return {
            "can_resume": len(suggestions) > 0,
            "failed_step_id": failed_step.get("step_id"),
            "diagnosis": error_message,
            "suggestions": suggestions,
            "healed_step": {
                **failed_step,
                "params": healed_params
            }
        }
