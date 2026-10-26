import os
import json
import uuid
import shutil
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
_BACKEND_DIR = Path(__file__).resolve().parent
for _p in [_BACKEND_DIR, _BACKEND_DIR / "core", _BACKEND_DIR / "gateway", _BACKEND_DIR / "planner"]:
    _p_str = str(_p)
    if _p_str not in sys.path:
        sys.path.insert(0, _p_str)

from config import settings
from gateway.router import GatewayRouter
from gateway.cache import PlanCache
from core.registry import ActionRegistry
from core.manifest import WorkspaceManifest
from core.grounding import GroundingChecker
from core.verifier import PlanVerifier
from core.dryrun import DryRunSimulator
from core.executor import PlanExecutor
from core.ledger import ExecutionLedger
from planner.ensemble import PlannerEnsemble
from planner.arbiter import PlanArbiter
from planner.explain import PlanExplainer

app = FastAPI(
    title="TrustFlow Deterministic Multi-LLM Execution Engine",
    description="Safety-bounded agentic planning, multi-LLM routing, and sandbox execution",
    version="1.0.0"
)

# CORS configuration: read from ALLOWED_ORIGINS env var, never use "*"
raw_origins = os.getenv("ALLOWED_ORIGINS", "")
if raw_origins.strip():
    allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip() and o.strip() != "*"]
else:
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://trustflow-frontend.davishtalreja.workers.dev",
        "https://hacktober-fest.onrender.com"
    ]

# Strictly reject wildcard
allowed_origins = [o for o in allowed_origins if o != "*"]
if not allowed_origins:
    allowed_origins = ["http://localhost:3000", "http://localhost:5500", "http://127.0.0.1:5500"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths and workspace initialization
WORKSPACE_PATH = Path(settings.WORKSPACE_PATH)
SEED_PATH = Path(settings.SEED_PATH)
WORKSPACE_RUNS_PATH = Path(getattr(settings, "WORKSPACE_RUNS_PATH", settings.BASE_DIR / "workspace_runs"))


def cleanup_old_workspace_runs(max_age_seconds: int = 3600):
    """Cleans up temporary run copies older than 1 hour on startup."""
    PlanExecutor.cleanup_old_runs(WORKSPACE_RUNS_PATH, max_age_seconds=max_age_seconds)


def initialize_workspace():
    WORKSPACE_PATH.mkdir(parents=True, exist_ok=True)
    WORKSPACE_RUNS_PATH.mkdir(parents=True, exist_ok=True)
    cleanup_old_workspace_runs(3600)
    if SEED_PATH.exists():
        for item in SEED_PATH.glob("*.csv"):
            dest = WORKSPACE_PATH / item.name
            if not dest.exists():
                shutil.copy(item, dest)


initialize_workspace()


# Event Manager for Server-Sent Events (SSE)
class RunEventManager:
    def __init__(self):
        self._listeners: Dict[str, List[asyncio.Queue]] = {}
        self._history: Dict[str, List[Dict[str, Any]]] = {}
        self._completed: Dict[str, bool] = {}

    def get_history(self, run_id: str) -> List[Dict[str, Any]]:
        return list(self._history.get(run_id, []))

    def add_listener(self, run_id: str, q: asyncio.Queue):
        if run_id not in self._listeners:
            self._listeners[run_id] = []
        self._listeners[run_id].append(q)

    def remove_listener(self, run_id: str, q: asyncio.Queue):
        if run_id in self._listeners:
            if q in self._listeners[run_id]:
                self._listeners[run_id].remove(q)
            if not self._listeners[run_id]:
                del self._listeners[run_id]

    def publish(self, run_id: str, event: Dict[str, Any]):
        if run_id not in self._history:
            self._history[run_id] = []
        self._history[run_id].append(event)
        if run_id in self._listeners:
            for q in self._listeners[run_id]:
                q.put_nowait(event)

    def complete(self, run_id: str):
        self._completed[run_id] = True
        if run_id in self._listeners:
            for q in self._listeners[run_id]:
                q.put_nowait({"status": "_DONE_"})


run_events = RunEventManager()

# Subsystem initializations
manifest = WorkspaceManifest(WORKSPACE_PATH)
grounding_checker = GroundingChecker(manifest)
verifier = PlanVerifier()
router = GatewayRouter(mock_mode=settings.MOCK_LLM_MODE)
cache = PlanCache()
ensemble = PlannerEnsemble(router)
arbiter = PlanArbiter(verifier, grounding_checker)
dryrun_simulator = DryRunSimulator(WORKSPACE_PATH)
ledger = ExecutionLedger(WORKSPACE_PATH / "ledger.json")
executor = PlanExecutor(
    workspace_path=WORKSPACE_PATH,
    ledger=ledger,
    seed_path=SEED_PATH,
    runs_dir=WORKSPACE_RUNS_PATH,
    isolate_sessions=True
)


# Request Models
class PlanRequest(BaseModel):
    request: str
    use_cache: bool = True


class ExecuteRequest(BaseModel):
    plan: Dict[str, Any]
    dry_run_first: bool = True
    run_id: Optional[str] = None


UNSAFE_PATTERNS = [
    "os.system", "eval(", "exec(", "subprocess", "__import__",
    "rm -rf", "shutil.rmtree", "powershell", "/bin/sh", "/bin/bash",
    "chmod ", "sudo ", "curl ", "wget ", "format ", "dd if=",
    "drop database", "shutdown", "reboot", "kill -9"
]


def is_request_unsafe(prompt: str) -> bool:
    prompt_lower = prompt.lower()
    return any(p in prompt_lower for p in UNSAFE_PATTERNS)


@app.get("/api/health")
async def health_check():
    """Health check endpoint confirming backend, router, and sandbox are online."""
    return {
        "status": "healthy",
        "service": "trustflow-engine",
        "backend": "online",
        "router": {
            "status": "online",
            "primary_planner": getattr(settings, "DEFAULT_PLANNER_PROVIDER", "gemini"),
            "fallback_critic": getattr(settings, "CRITIC_PROVIDER", "groq"),
            "cerebras_bypassed": True
        },
        "sandbox": {
            "status": "online",
            "execution_mode": "strictly_whitelisted",
            "arbitrary_execution_prohibited": True,
            "allowed_extensions": [".csv", ".txt", ".md", ".json"]
        },
        "environment": settings.ENVIRONMENT,
        "mock_mode": settings.MOCK_LLM_MODE,
        "actions_available": len(ActionRegistry.get_all_actions()),
        "workspace_path": str(WORKSPACE_PATH)
    }


@app.get("/api/actions")
async def get_actions():
    """
    Returns the full list of available actions from the registry
    with their descriptions and read/write permission tags.
    """
    actions_list = ActionRegistry.get_actions_list()
    return {
        "status": "ok",
        "actions": actions_list,
        "count": len(actions_list)
    }


@app.get("/api/manifest")
async def get_manifest():
    """Returns workspace file headers and column names only (no row data)."""
    return manifest.scan()


@app.post("/api/reset-workspace")
async def reset_workspace():
    """Resets workspace datasets from workspace_seed."""
    initialize_workspace()
    return {"status": "workspace_reset_successful", "manifest": manifest.scan()}


@app.get("/api/benchmark")
async def get_benchmark_results():
    """
    Returns the contents of eval/results.json if it exists.
    Run `python eval/run_eval.py` to generate it.
    """
    results_path = Path(settings.BASE_DIR).parent / "eval" / "results.json"
    if not results_path.exists():
        raise HTTPException(
            status_code=404,
            detail="eval/results.json not found. Run: python eval/run_eval.py"
        )
    with open(results_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/plan")
async def create_plan(payload: PlanRequest):
    """
    Accepts natural language intent.
    Injects a strict deterministic compiler system prompt to the LLM (Gemini/Groq).
    Breaks the intent down into an ordered JSON array of steps using only ACTION_REGISTRY.
    If the request is unsafe, returns a rejection JSON.
    """
    user_prompt = payload.request.strip()
    if not user_prompt:
        raise HTTPException(status_code=400, detail="Request prompt cannot be empty.")

    # 1. Prohibit arbitrary shell commands, os.system(), eval(), or unsafe intent
    if is_request_unsafe(user_prompt):
        return {
            "status": "rejected",
            "rejected": True,
            "error": "Unsafe request: Arbitrary shell commands, system calls, and eval() are strictly prohibited. Operations must use the whitelisted ACTION_REGISTRY.",
            "reason": "prohibited_operation",
            "plan": None,
            "steps": [],
            "explanation": "Request was rejected by TrustFlow deterministic security policy because it requested arbitrary code execution or prohibited system operations."
        }

    # 2. Check pre-warmed plan cache
    if payload.use_cache and settings.ENABLE_CACHE:
        cached_plan = cache.get(user_prompt)
        if cached_plan:
            explanation = PlanExplainer.explain(cached_plan)
            return {
                "source": "cache",
                "plan": cached_plan,
                "explanation": explanation,
                "verified": True,
                "issues": []
            }

    # 3. Run ensemble planners (Gemini primary, Groq fallback)
    ws_meta = manifest.scan()
    plan_a, plan_b = await ensemble.generate_dual_plans(user_prompt, ws_meta)

    # 4. Arbiter consensus & selection
    arb_result = arbiter.arbitrate(user_prompt, plan_a, plan_b)
    selected_plan = arb_result["selected_plan"]

    # Check if LLM emitted a rejection plan
    if selected_plan.get("rejected") or selected_plan.get("status") == "rejected":
        return {
            "status": "rejected",
            "rejected": True,
            "error": selected_plan.get("error", "Unsafe request: Prohibited operation outside ACTION_REGISTRY whitelist."),
            "reason": selected_plan.get("reason", "prohibited_operation"),
            "plan": selected_plan,
            "steps": [],
            "explanation": "Plan compilation was rejected because the request violates sandbox constraints."
        }

    # 5. Generate human explanation (back-translation)
    explanation = PlanExplainer.explain(selected_plan)

    return {
        "status": "planned",
        "source": arb_result["chosen_source"],
        "consensus": arb_result["consensus"],
        "plan": selected_plan,
        "explanation": explanation,
        "issues": arb_result["validation_issues"]
    }


@app.post("/api/dryrun")
async def dry_run_plan(plan: Dict[str, Any]):
    """Simulates a plan completely in-memory without persistent disk side-effects."""
    ver_res = verifier.verify(plan)
    if not ver_res.is_valid:
        raise HTTPException(status_code=400, detail={"verification_errors": ver_res.errors})

    result = dryrun_simulator.simulate(plan)
    return result.to_dict()


@app.post("/api/execute")
async def execute_plan(payload: ExecuteRequest):
    """
    Accepts LLM-generated JSON plan (simulating post-human approval).
    Iterates through the steps and verifies each action exists in the ACTION_REGISTRY.
    If valid, executes the mapped Python function and appends the result to an execution trace.
    If an action is missing or throws an error (e.g., FileNotFoundError), halts execution,
    catches the stack trace, and triggers a self-repair JSON response.
    """
    plan = payload.plan
    run_id = payload.run_id or str(uuid.uuid4())
    steps = plan.get("steps", [])

    # 1. Verify every step action exists in ACTION_REGISTRY
    for idx, step in enumerate(steps):
        action = step.get("action")
        if not action or not ActionRegistry.is_valid_action(action):
            error_msg = f"Security Violation: Action '{action}' is missing or not in the allowed ACTION_REGISTRY. Arbitrary shell commands and eval() are strictly prohibited."
            tb = f"SecurityException: Prohibited action '{action}' at step index {idx}"
            heal_info = {
                "can_resume": False,
                "failed_step_id": step.get("step_id", idx + 1),
                "diagnosis": error_msg,
                "suggestions": [f"Replace '{action}' with a whitelisted action from ACTION_REGISTRY."]
            }
            return {
                "success": False,
                "status": "halted_with_error",
                "run_id": run_id,
                "failed_step": step.get("step_id", idx + 1),
                "action": action,
                "error": error_msg,
                "traceback": tb,
                "self_repair": heal_info,
                "execution_trace": [{
                    "step_id": step.get("step_id", idx + 1),
                    "action": action,
                    "status": "FAILED",
                    "error": error_msg,
                    "traceback": tb,
                    "heal_suggestion": heal_info
                }],
                "steps": [{
                    "step_id": step.get("step_id", idx + 1),
                    "action": action,
                    "status": "FAILED",
                    "error": error_msg,
                    "heal_suggestion": heal_info
                }]
            }

    # 2. Structural & safety verification
    ver_res = verifier.verify(plan)
    if not ver_res.is_valid:
        error_msg = f"Verification failed: {'; '.join(ver_res.errors)}"
        heal_info = {
            "can_resume": False,
            "diagnosis": error_msg,
            "suggestions": ["Correct plan structure and parameter types to match action definitions."]
        }
        return {
            "success": False,
            "status": "halted_with_error",
            "run_id": run_id,
            "error": error_msg,
            "traceback": "VerificationError: Plan did not pass deterministic verification",
            "self_repair": heal_info,
            "execution_trace": [],
            "steps": []
        }

    # 3. Optional dry-run check
    if payload.dry_run_first:
        dry_result = dryrun_simulator.simulate(plan)
        if not dry_result.success:
            return {
                "success": False,
                "status": "halted_with_error",
                "run_id": run_id,
                "error": f"Dry-run simulation failed: {dry_result.error}",
                "traceback": "DryRunSimulationError: Pre-flight simulation failed",
                "self_repair": {
                    "can_resume": False,
                    "diagnosis": dry_result.error,
                    "suggestions": ["Resolve dry-run dataset mismatch before executing."]
                },
                "execution_trace": [],
                "steps": []
            }

    # 4. Isolated Execution
    loop = asyncio.get_running_loop()

    def sync_event_callback(evt: Dict[str, Any]):
        loop.call_soon_threadsafe(run_events.publish, run_id, evt)

    run_executor = PlanExecutor(
        workspace_path=WORKSPACE_PATH,
        ledger=ledger,
        seed_path=SEED_PATH,
        runs_dir=WORKSPACE_RUNS_PATH,
        isolate_sessions=True,
        event_callback=sync_event_callback
    )

    try:
        execution_result = await asyncio.to_thread(run_executor.execute, plan, run_id=run_id)
    finally:
        run_events.complete(run_id)

    # If any step failed, halt execution, catch stack trace, and trigger self-repair JSON response
    if not execution_result.get("success", False):
        failed_step = next((s for s in execution_result.get("steps", []) if s.get("status") == "FAILED"), None)
        return {
            "success": False,
            "status": "halted_with_error",
            "run_id": run_id,
            "failed_step": failed_step.get("step_id") if failed_step else None,
            "action": failed_step.get("action") if failed_step else None,
            "error": failed_step.get("error") if failed_step else "Execution failed",
            "traceback": failed_step.get("traceback") if failed_step else None,
            "self_repair": failed_step.get("heal_suggestion") if failed_step else None,
            "execution_trace": execution_result.get("steps", []),
            "steps": execution_result.get("steps", []),
            "run_log": execution_result.get("run_log", [])
        }

    return {
        "success": True,
        "status": "completed",
        "run_id": run_id,
        "execution_trace": execution_result.get("steps", []),
        "steps": execution_result.get("steps", []),
        "run_log": execution_result.get("run_log", [])
    }


@app.get("/api/runs/{run_id}/events")
async def stream_run_events(run_id: str):
    """
    Server-Sent Events endpoint emitting real-time run execution events as they happen.
    """
    async def event_generator():
        # Replay any prior events for this run
        for evt in run_events.get_history(run_id):
            yield f"data: {json.dumps(evt)}\n\n"

        if run_events._completed.get(run_id, False):
            return

        q: asyncio.Queue = asyncio.Queue()
        run_events.add_listener(run_id, q)
        try:
            while True:
                try:
                    evt = await asyncio.wait_for(q.get(), timeout=20.0)
                    if isinstance(evt, dict) and evt.get("status") == "_DONE_":
                        break
                    yield f"data: {json.dumps(evt)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            run_events.remove_listener(run_id, q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/ledger")
async def get_ledger():
    """Returns execution history and data lineage logs."""
    return ledger.get_records()
