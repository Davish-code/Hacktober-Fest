from typing import Dict, Any, List


class PlanExplainer:
    """
    Back-translates structured JSON plans into clear, transparent
    natural language explanations for human review and auditing.
    """

    @classmethod
    def explain(cls, plan: Dict[str, Any]) -> str:
        intent = plan.get("intent", "Execute workspace data operations")
        steps = plan.get("steps", [])

        if not steps:
            return f"Plan for '{intent}': No steps defined."

        lines = [f"### Execution Plan: {intent}\n"]
        lines.append("Here is the deterministic step-by-step procedure:")

        for s in steps:
            s_id = s.get("step_id")
            action = s.get("action")
            params = s.get("params", {})
            desc = s.get("description", "")

            explanation = cls._explain_step(action, params)
            lines.append(f"**Step {s_id} [{action}]**: {desc or explanation}")

        return "\n".join(lines)

    @classmethod
    def _explain_step(cls, action: str, params: Dict[str, Any]) -> str:
        if action == "READ_CSV":
            limit = f" (first {params['limit']} rows)" if params.get("limit") else ""
            return f"Load dataset `{params.get('file')}` into memory{limit}."
        elif action == "FILTER_ROWS":
            return f"Filter records where column `{params.get('column')}` {params.get('operator')} '{params.get('value')}'."
        elif action == "SELECT_COLUMNS":
            cols = ", ".join(f"`{c}`" for c in params.get("columns", []))
            return f"Retain only columns: {cols}."
        elif action == "JOIN_DATA":
            return f"Merge `{params.get('left_file')}` with `{params.get('right_file')}` on `{params.get('left_on')}` == `{params.get('right_on')}`."
        elif action == "AGGREGATE":
            return f"Group data by `{params.get('group_by')}` and calculate `{params.get('func')}` of `{params.get('agg_col')}`."
        elif action == "SORT_ROWS":
            direction = "ascending" if params.get("ascending", True) else "descending"
            return f"Sort entries by column `{params.get('column')}` ({direction})."
        elif action == "EXPORT_CSV":
            return f"Write output dataset to workspace file `{params.get('output_file')}`."
        elif action == "GENERATE_SUMMARY":
            return "Generate statistical overview and row counts."
        return f"Execute operation `{action}` with parameters {params}."
