import sys
import os
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)
except Exception as e:
    print(f"Failed to initialize TestClient: {e}")
    client = None


def run_smoke_test():
    print("=" * 60)
    print("RUNNING SMOKE TEST SUITE: Hacktober-Fest Engine")
    print("=" * 60)

    if client is None:
        print("[FAIL] Smoke test aborted: test client could not be loaded.")
        sys.exit(1)

    # 1. Test /api/health
    print("\n[1/4] Testing Health Endpoint (/api/health)...")
    res = client.get("/api/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    health_data = res.json()
    print(f"  [OK] Health Status: {health_data['status']}")
    print(f"  [OK] Actions Available: {health_data['actions_available']}")

    # 2. Test /api/plan
    print("\n[2/4] Testing Plan Generation (/api/plan)...")
    demo_request = "Filter customers from USA and export to usa_customers.csv"
    res = client.post("/api/plan", json={"request": demo_request, "use_cache": True})
    assert res.status_code == 200, f"Plan generation failed: {res.text}"
    plan_data = res.json()
    plan = plan_data["plan"]
    print(f"  [OK] Plan Source: {plan_data['source']}")
    print(f"  [OK] Steps Generated: {len(plan.get('steps', []))}")
    print(f"  [OK] Intent: {plan.get('intent')}")

    # 3. Test /api/dryrun
    print("\n[3/4] Testing Dry-Run Simulation (/api/dryrun)...")
    res = client.post("/api/dryrun", json=plan)
    assert res.status_code == 200, f"Dry-run simulation failed: {res.text}"
    dryrun_data = res.json()
    assert dryrun_data["success"] is True, f"Dryrun failed: {dryrun_data.get('error')}"
    print(f"  [OK] Dry-run completed with zero side effects: {len(dryrun_data['steps'])} steps simulated")

    # 4. Test /api/execute
    print("\n[4/4] Testing Execution (/api/execute)...")
    res = client.post("/api/execute", json={"plan": plan, "dry_run_first": True})
    assert res.status_code == 200, f"Execution failed: {res.text}"
    exec_data = res.json()
    assert exec_data["success"] is True, f"Execution failed: {exec_data}"
    print(f"  [OK] Execution successful! Run ID: {exec_data['run_id']}")
    for step in exec_data["steps"]:
        print(f"    - Step {step['step_id']} [{step['action']}]: {step['status']}")

    print("\n" + "=" * 60)
    print("ALL SMOKE TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_smoke_test()
