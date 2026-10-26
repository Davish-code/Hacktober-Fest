import hashlib
import json
from typing import Dict, Any, Optional


class PlanCache:
    """
    In-memory plan cache with pre-warmed deterministic responses for instant demo runs.
    """

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._prewarm_demo_plans()

    def _hash_key(self, prompt: str) -> str:
        return hashlib.sha256(prompt.strip().lower().encode("utf-8")).hexdigest()

    def get(self, prompt: str) -> Optional[Dict[str, Any]]:
        key = self._hash_key(prompt)
        return self._cache.get(key)

    def set(self, prompt: str, plan: Dict[str, Any]):
        key = self._hash_key(prompt)
        self._cache[key] = plan

    def _prewarm_demo_plans(self):
        # Pre-warmed demo queries
        demo_queries = [
            (
                "Filter customers from USA and export to usa_customers.csv",
                {
                    "intent": "Filter customers by USA and export to usa_customers.csv",
                    "steps": [
                        {
                            "step_id": 1,
                            "action": "READ_CSV",
                            "params": {"file": "customers.csv"},
                            "description": "Read customers.csv"
                        },
                        {
                            "step_id": 2,
                            "action": "FILTER_ROWS",
                            "params": {"file": "customers.csv", "column": "country", "operator": "==", "value": "USA"},
                            "description": "Filter rows where country == USA"
                        },
                        {
                            "step_id": 3,
                            "action": "EXPORT_CSV",
                            "params": {"source_step": 2, "output_file": "usa_customers.csv"},
                            "description": "Export filtered customers to usa_customers.csv"
                        }
                    ]
                }
            ),
            (
                "Calculate total order amount by customer and save to totals.csv",
                {
                    "intent": "Calculate total order amount grouped by customer_id",
                    "steps": [
                        {
                            "step_id": 1,
                            "action": "READ_CSV",
                            "params": {"file": "orders.csv"},
                            "description": "Read orders.csv"
                        },
                        {
                            "step_id": 2,
                            "action": "AGGREGATE",
                            "params": {"file": "orders.csv", "group_by": "customer_id", "agg_col": "amount", "func": "sum"},
                            "description": "Aggregate sum of amount by customer_id"
                        },
                        {
                            "step_id": 3,
                            "action": "EXPORT_CSV",
                            "params": {"source_step": 2, "output_file": "totals.csv"},
                            "description": "Export aggregated totals"
                        }
                    ]
                }
            )
        ]

        for query, plan in demo_queries:
            self.set(query, plan)
