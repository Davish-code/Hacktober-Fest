"""
Unit test for TrustFlow sandbox path safety.
Tests that path escapes, invalid extensions, and forbidden targets are strictly rejected.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.core.executor import PlanExecutor


def test_sandbox_path_rejection():
    print("Running sandbox path rejection unit tests...")
    ws = ROOT / "backend" / "workspace"
    executor = PlanExecutor(ws, isolate_sessions=False)

    malicious_paths = [
        "../../etc/passwd.csv",
        "C:\\Windows\\x.csv",
        "/etc/passwd"
    ]

    for p in malicious_paths:
        rejected = False
        error_msg = ""
        try:
            executor.resolve_safe_path(p)
        except ValueError as e:
            rejected = True
            error_msg = str(e)
        except Exception as e:
            rejected = True
            error_msg = f"Unexpected error type: {type(e).__name__}: {e}"

        assert rejected, f"Security failure: Path '{p}' was NOT rejected by resolve_safe_path!"
        print(f"  [OK] Successfully rejected '{p}': {error_msg}")

    # Also test via execute step
    for p in malicious_paths:
        plan = {
            "steps": [
                {
                    "step_id": 1,
                    "action": "READ_CSV",
                    "params": {"file": p}
                }
            ]
        }
        res = executor.execute(plan)
        assert not res["success"], f"Security failure: Plan execution with '{p}' unexpectedly succeeded!"
        assert res["steps"][0]["status"] == "FAILED"
        print(f"  [OK] Plan step execution with '{p}' safely failed with status FAILED")

    # Verify allowed paths succeed
    safe_file = executor.resolve_safe_path("customers.csv")
    assert safe_file.name == "customers.csv"
    print("  [OK] Safe path 'customers.csv' resolved correctly")

    print("\nALL SANDBOX SECURITY TESTS PASSED!")


if __name__ == "__main__":
    test_sandbox_path_rejection()
