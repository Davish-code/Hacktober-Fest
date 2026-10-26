import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional


class ExecutionLedger:
    """
    Append-only run log and data lineage ledger.
    Maintains an audit trail of executed plans, hashes, inputs, and outputs.
    """

    def __init__(self, ledger_file: Path):
        self.ledger_file = Path(ledger_file)
        self.ledger_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.ledger_file.exists():
            with open(self.ledger_file, "w", encoding="utf-8") as f:
                json.dump([], f)

    def record_run(
        self,
        run_id: str,
        plan: Dict[str, Any],
        results: List[Dict[str, Any]],
        success: bool,
        run_log: Optional[List[Dict[str, Any]]] = None
    ):
        entry = {
            "run_id": run_id,
            "timestamp": time.time(),
            "iso_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "success": success,
            "plan_intent": plan.get("intent", ""),
            "steps_count": len(plan.get("steps", [])),
            "step_results": results,
            "run_log": run_log or []
        }

        records = self.get_records()
        records.append(entry)
        with open(self.ledger_file, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

    def get_records(self) -> List[Dict[str, Any]]:
        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
