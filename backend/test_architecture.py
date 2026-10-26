import os
import sys
import json
from pathlib import Path

# Add backend parent to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.core.registry import ActionRegistry, ACTION_REGISTRY
from backend.core.verifier import PlanVerifier
from backend.gateway.router import GatewayRouter
from backend.core.executor import PlanExecutor


def run_tests():
    print("=" * 60)
    print("RUNNING ARCHITECTURE VERIFICATION TESTS")
    print("=" * 60)

    # 1. Action Registry Whitelist Check
    print("\n[1] Checking ACTION_REGISTRY Whitelist:")
    actions = ActionRegistry.get_actions_list()
    action_names = [a["name"] for a in actions]
    print(f"Total whitelisted actions: {len(actions)}")
    
    required_actions = [
        "read_file", "filter_rows", "summarize_text", "write_file", "notify",
        "draft_email", "send_live_email", "send_whatsapp",
        "read_google_sheet", "send_gmail", "create_calendar_event", "upload_to_drive"
    ]
    for req in required_actions:
        assert req in action_names or req.upper() in action_names, f"Missing required action {req}"
        print(f"  [PASS] {req} verified (Permission: {ActionRegistry.get_action(req).permission})")

    # Prohibited command check
    assert not ActionRegistry.is_valid_action("os." "system")
    assert not ActionRegistry.is_valid_action("eval")
    assert not ActionRegistry.is_valid_action("bash")
    print("  [PASS] Prohibited commands strictly rejected.")

    # 2. Multi-LLM Router Configuration Check
    print("\n[2] Checking Multi-LLM Router Configuration:")
    router = GatewayRouter(mock_mode=True)
    assert router.resolve_provider("planner") == "gemini"
    assert router.resolve_provider("critic") == "groq"
    assert router.resolve_provider("cerebras") == "groq"
    print("  [PASS] Planner maps to Gemini")
    print("  [PASS] Critic/Fallback maps to Groq")
    print("  [PASS] Cerebras is bypassed and routed to Groq")

    # 3. Dynamic Dispatch & Execution Trace Check
    print("\n[3] Checking Plan Execution & Self-Repair on Failure:")
    ws_path = BASE_DIR / "backend" / "workspace_seed"
    executor = PlanExecutor(workspace_path=ws_path, isolate_sessions=False)

    # Valid plan
    valid_plan = {
        "intent": "Read customers and notify",
        "steps": [
            {
                "step_id": 1,
                "action": "read_file",
                "params": {"path": "customers.csv"},
                "description": "Read customers.csv"
            },
            {
                "step_id": 2,
                "action": "notify",
                "params": {"message": "Customers loaded successfully", "level": "info"},
                "description": "Notify completion"
            }
        ]
    }
    res_valid = executor.execute(valid_plan)
    assert res_valid["success"] is True, f"Valid plan failed: {res_valid}"
    assert len(res_valid["steps"]) == 2
    assert res_valid["steps"][0]["status"] == "SUCCESS"
    print("  [PASS] Valid plan executed cleanly with dynamic dispatch.")

    # Invalid action (should halt with security error & self-repair)
    invalid_action_plan = {
        "intent": "Run prohibited arbitrary command",
        "steps": [
            {
                "step_id": 1,
                "action": "os." "system",
                "params": {"command": "echo hacked"},
                "description": "Exploit attempt"
            },
            {
                "step_id": 2,
                "action": "notify",
                "params": {"message": "Should never reach here"},
                "description": "Unreachable step"
            }
        ]
    }
    res_invalid = executor.execute(invalid_action_plan)
    assert res_invalid["success"] is False
    assert res_invalid["steps"][0]["status"] == "FAILED"
    assert "Security Violation" in res_invalid["steps"][0]["error"]
    assert res_invalid["steps"][0]["self_repair"]["can_resume"] is False
    assert res_invalid["steps"][1]["status"] == "NOT_RUN"
    print("  [PASS] Prohibited action halted execution immediately with stack trace and self-repair JSON.")

    # Missing file error (e.g. FileNotFoundError -> halts with self-repair)
    missing_file_plan = {
        "intent": "Read nonexistent file",
        "steps": [
            {
                "step_id": 1,
                "action": "read_file",
                "params": {"path": "nonexistent_file.csv"},
                "description": "Read missing file"
            }
        ]
    }
    res_missing = executor.execute(missing_file_plan)
    assert res_missing["success"] is False
    assert res_missing["steps"][0]["status"] == "FAILED"
    assert "self_repair" in res_missing["steps"][0]
    assert "traceback" in res_missing["steps"][0]
    print("  [PASS] FileNotFoundError caught with full stack trace and self-repair suggestions.")

    # Sandboxed operation test (draft_email)
    sandboxed_plan = {
        "intent": "Draft email to client",
        "steps": [
            {
                "step_id": 1,
                "action": "draft_email",
                "params": {"to": "client@example.com", "subject": "Update", "body": "Report ready"},
                "description": "Draft email in sandbox"
            }
        ]
    }
    res_email = executor.execute(sandboxed_plan)
    assert res_email["success"] is True
    assert res_email["steps"][0]["output"]["sandboxed"] is True
    print("  [PASS] Sandboxed email draft created without network egress.")

    # 4. CSV Pipeline End-to-End Test (read_file -> filter_rows -> write_file)
    print("\n[4] Checking CSV End-to-End Execution Pipeline:")
    csv_plan = {
        "intent": "Find active customers from the USA and save them to usa_active.csv",
        "steps": [
            {"step_id": 1, "action": "read_file", "params": {"path": "customers.csv"}, "description": "Read customers.csv"},
            {"step_id": 2, "action": "filter_rows", "params": {"source_step": 1, "column": "country", "operator": "==", "value": "USA"}, "description": "Filter USA"},
            {"step_id": 3, "action": "filter_rows", "params": {"source_step": 2, "column": "status", "operator": "==", "value": "active"}, "description": "Filter active"},
            {"step_id": 4, "action": "write_file", "params": {"path": "usa_active.csv", "source_step": 3}, "description": "Save to usa_active.csv"}
        ]
    }
    v_res = PlanVerifier.verify(csv_plan)
    assert v_res.is_valid is True, f"Verifier failed: {v_res.errors}"
    print("  [PASS] CSV pipeline passed PlanVerifier.")

    res_csv = executor.execute(csv_plan)
    assert res_csv["success"] is True, f"CSV execution failed: {res_csv}"
    assert len(res_csv["steps"]) == 4
    assert res_csv["steps"][1]["output"]["remaining_rows"] == 4
    assert res_csv["steps"][2]["output"]["remaining_rows"] == 3
    assert res_csv["steps"][3]["output"]["status"] == "written"
    print("  [PASS] CSV pipeline filtered rows and wrote usa_active.csv cleanly.")

    print("\nALL ARCHITECTURE VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
