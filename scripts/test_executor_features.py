"""
Comprehensive tests for executor features:
- Retries (0-3, backoff)
- Fallback
- on_failure ("abort" and "continue")
- Conditions ("if": ref/op/value)
- Event log statuses (started, ok, retry, fallback, skipped, failed, not_run)
- Session isolation
- SSE endpoint (/api/runs/{run_id}/events)
"""
import sys
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.core.executor import PlanExecutor
from fastapi.testclient import TestClient
from backend.main import app


def test_executor_features():
    print("Running executor feature test suite...")

    seed_dir = ROOT / "backend" / "workspace_seed"
    runs_dir = ROOT / "backend" / "workspace_runs"
    executor = PlanExecutor(ROOT / "backend" / "workspace", seed_path=seed_dir, runs_dir=runs_dir, isolate_sessions=True)

    # 1. Test Condition ("if") skipped
    print("\n[Test 1] Testing step condition (if) -> skipped...")
    plan_condition = {
        "steps": [
            {
                "step_id": 1,
                "action": "READ_CSV",
                "params": {"file": "customers.csv"}
            },
            {
                "step_id": 2,
                "action": "FILTER_ROWS",
                "params": {"source_step": 1, "column": "country", "operator": "==", "value": "USA"},
                "if": {"ref": "step_1.rows", "op": "<", "value": 0}  # False, rows is > 0
            }
        ]
    }
    res = executor.execute(plan_condition)
    assert res["success"] is True
    assert res["steps"][0]["status"] == "SUCCESS"
    assert res["steps"][1]["status"] == "SKIPPED"
    statuses = [e["status"] for e in res["run_log"] if e["step_id"] == 2]
    assert "skipped" in statuses, f"Expected skipped status in log, got: {statuses}"
    print("  [OK] Step condition evaluated to False and step was marked SKIPPED")

    # 2. Test Retries
    print("\n[Test 2] Testing retries...")
    plan_retry = {
        "steps": [
            {
                "step_id": 1,
                "action": "READ_CSV",
                "params": {"file": "non_existent.csv"},
                "retries": 2
            }
        ]
    }
    res_retry = executor.execute(plan_retry)
    assert not res_retry["success"]
    retry_events = [e for e in res_retry["run_log"] if e["status"] == "retry"]
    assert len(retry_events) == 2, f"Expected 2 retry events, got {len(retry_events)}"
    print(f"  [OK] Successfully recorded {len(retry_events)} retries before failure")

    # 3. Test Fallback
    print("\n[Test 3] Testing fallback...")
    plan_fallback = {
        "steps": [
            {
                "step_id": 1,
                "action": "READ_CSV",
                "params": {"file": "non_existent.csv"},
                "retries": 1,
                "fallback": {
                    "action": "READ_CSV",
                    "params": {"file": "customers.csv"}
                }
            }
        ]
    }
    res_fallback = executor.execute(plan_fallback)
    assert res_fallback["success"] is True
    assert res_fallback["steps"][0]["status"] == "SUCCESS"
    assert res_fallback["steps"][0]["fallback_used"] == "READ_CSV"
    fb_events = [e for e in res_fallback["run_log"] if e["status"] == "fallback"]
    assert len(fb_events) == 1
    print("  [OK] Fallback action triggered and succeeded")

    # 4. Test on_failure: abort vs continue
    print("\n[Test 4] Testing on_failure ('abort' and 'continue')...")
    # Abort
    plan_abort = {
        "steps": [
            {
                "step_id": 1,
                "action": "READ_CSV",
                "params": {"file": "missing.csv"},
                "on_failure": "abort"
            },
            {
                "step_id": 2,
                "action": "READ_CSV",
                "params": {"file": "customers.csv"}
            }
        ]
    }
    res_abort = executor.execute(plan_abort)
    assert not res_abort["success"]
    assert res_abort["steps"][1]["status"] == "NOT_RUN"
    not_run_events = [e for e in res_abort["run_log"] if e["status"] == "not_run"]
    assert len(not_run_events) == 1
    print("  [OK] on_failure='abort' marked subsequent step as NOT_RUN")

    # Continue
    plan_continue = {
        "steps": [
            {
                "step_id": 1,
                "action": "READ_CSV",
                "params": {"file": "missing.csv"},
                "on_failure": "continue"
            },
            {
                "step_id": 2,
                "action": "READ_CSV",
                "params": {"file": "customers.csv"}
            }
        ]
    }
    res_continue = executor.execute(plan_continue)
    assert res_continue["steps"][0]["status"] == "FAILED"
    assert res_continue["steps"][1]["status"] == "SUCCESS"
    print("  [OK] on_failure='continue' allowed subsequent step to execute")

    # 5. Test Session Isolation: Seed directory is untouched
    print("\n[Test 5] Testing session isolation...")
    seed_files_before = set(f.name for f in seed_dir.glob("*"))
    plan_export = {
        "steps": [
            {
                "step_id": 1,
                "action": "READ_CSV",
                "params": {"file": "customers.csv"}
            },
            {
                "step_id": 2,
                "action": "EXPORT_CSV",
                "params": {"source_step": 1, "output_file": "isolated_test_output.csv"}
            }
        ]
    }
    res_export = executor.execute(plan_export)
    assert res_export["success"] is True
    seed_files_after = set(f.name for f in seed_dir.glob("*"))
    assert seed_files_before == seed_files_after, "Seed directory was modified during execution!"
    assert not (seed_dir / "isolated_test_output.csv").exists(), "Exported file leaked into seed directory!"
    print("  [OK] Seed directory remained completely untouched and pristine")

    # 6. Test SSE Endpoint
    print("\n[Test 6] Testing SSE events endpoint (/api/runs/{run_id}/events)...")
    client = TestClient(app)
    run_id = "test_sse_run_123"

    # Execute plan with specific run_id
    plan_sse = {
        "steps": [
            {
                "step_id": 1,
                "action": "READ_CSV",
                "params": {"file": "customers.csv"}
            }
        ]
    }
    exec_res = client.post("/api/execute", json={"plan": plan_sse, "dry_run_first": False, "run_id": run_id})
    assert exec_res.status_code == 200

    # Stream events from endpoint
    with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
        lines = [line for line in stream.iter_lines() if line]
        assert any("started" in l for l in lines)
        assert any("ok" in l for l in lines)
    print(f"  [OK] SSE stream correctly delivered execution events ({len(lines)} lines)")

    print("\nALL EXECUTOR FEATURE TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_executor_features()
