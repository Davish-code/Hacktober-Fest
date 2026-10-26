import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_endpoints():
    print("TESTING FASTAPI ENDPOINTS")
    print("-" * 50)

    # 1. GET /api/health
    res = requests.get(f"{BASE_URL}/api/health")
    assert res.status_code == 200, f"/api/health failed: {res.text}"
    health_data = res.json()
    assert health_data["backend"] == "online"
    assert health_data["router"]["status"] == "online"
    assert health_data["router"]["cerebras_bypassed"] is True
    assert health_data["sandbox"]["status"] == "online"
    print("[PASS] GET /api/health:", json.dumps(health_data, indent=2))

    # 2. GET /api/actions
    res = requests.get(f"{BASE_URL}/api/actions")
    assert res.status_code == 200, f"/api/actions failed: {res.text}"
    actions_data = res.json()
    assert actions_data["status"] == "ok"
    assert len(actions_data["actions"]) >= 12
    print(f"[PASS] GET /api/actions: returned {len(actions_data['actions'])} whitelisted actions with permission tags.")

    # 3. POST /api/plan with unsafe command
    res = requests.post(
        f"{BASE_URL}/api/plan",
        json={"request": "run os.system('rm -rf /') to clean up"}
    )
    assert res.status_code == 200
    plan_data = res.json()
    assert plan_data.get("rejected") is True
    assert plan_data.get("status") == "rejected"
    print("[PASS] POST /api/plan correctly rejected unsafe command:", plan_data["error"])

    # 4. POST /api/execute with prohibited action
    res = requests.post(
        f"{BASE_URL}/api/execute",
        json={
            "plan": {
                "intent": "Unsafe test",
                "steps": [
                    {"step_id": 1, "action": "eval", "params": {"code": "1+1"}, "description": "unsafe eval"}
                ]
            },
            "dry_run_first": False
        }
    )
    assert res.status_code == 200
    exec_data = res.json()
    assert exec_data["success"] is False
    assert exec_data["status"] == "halted_with_error"
    assert "Security Violation" in exec_data["error"]
    assert "self_repair" in exec_data
    assert "traceback" in exec_data
    print("[PASS] POST /api/execute caught prohibited action with stack trace & self-repair.")

    # 5. POST /api/execute with valid plan
    res = requests.post(
        f"{BASE_URL}/api/execute",
        json={
            "plan": {
                "intent": "Read and summarize",
                "steps": [
                    {"step_id": 1, "action": "read_file", "params": {"path": "customers.csv"}, "description": "Load data"},
                    {"step_id": 2, "action": "notify", "params": {"message": "Loaded customers"}, "description": "Notify"}
                ]
            },
            "dry_run_first": False
        }
    )
    assert res.status_code == 200
    exec_valid = res.json()
    assert exec_valid["success"] is True
    assert exec_valid["status"] == "completed"
    assert len(exec_valid["execution_trace"]) == 2
    print("[PASS] POST /api/execute ran valid plan with dynamic dispatch & returned execution trace.")

    print("-" * 50)
    print("ALL API ENDPOINT TESTS PASSED!")

if __name__ == "__main__":
    test_endpoints()
