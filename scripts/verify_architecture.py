"""TrustFlow architecture audit. Run from the repo root:
    python scripts/verify_architecture.py                 # static + import checks
    python scripts/verify_architecture.py --url http://localhost:8000   # + live checks
Exit code 1 if any FAIL."""
import importlib, json, re, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
results = []
def rec(level, name, detail=""): results.append((level, name, detail))
def read(p):
    f = ROOT / p
    return f.read_text(encoding="utf-8", errors="ignore") if f.exists() else ""
def py_files(folder):
    return [f for f in (ROOT / folder).rglob("*.py") if "__pycache__" not in f.parts] if (ROOT / folder).exists() else []

# 1. Structure ---------------------------------------------------------------
MUST = ["backend/main.py", "backend/config.py", "backend/requirements.txt", "backend/gateway/providers.py",
        "backend/gateway/router.py", "backend/core/registry.py", "backend/core/verifier.py",
        "backend/core/manifest.py", "backend/core/dryrun.py", "backend/core/executor.py",
        "backend/planner/prompts.py", "backend/planner/ensemble.py", "backend/planner/explain.py",
        "frontend/index.html", "frontend/app.js", "frontend/config.js", ".gitignore", ".env.example", "README.md"]
NICE = ["backend/gateway/governor.py", "backend/gateway/breaker.py", "backend/gateway/cache.py",
        "backend/core/grounding.py", "backend/core/healer.py", "backend/core/ledger.py",
        "backend/planner/arbiter.py", "eval/run_eval.py", "render.yaml", "LICENSE"]
for p in MUST: rec("PASS" if (ROOT / p).exists() else "FAIL", f"file {p}")
for p in NICE:
    if not (ROOT / p).exists(): rec("WARN", f"optional file missing: {p}")
for d in ["backend", "backend/gateway", "backend/core", "backend/planner"]:
    if (ROOT / d).exists() and not (ROOT / d / "__init__.py").exists():
        rec("WARN", f"{d}/__init__.py missing", "imports may fail on some setups")

# 2. Secrets and git hygiene ---------------------------------------------------
gi = read(".gitignore")
for pat in [".env", "__pycache__", ".idea", ".agents", ".gemini"]:
    rec("PASS" if pat in gi else "FAIL" if pat == ".env" else "WARN", f".gitignore covers {pat}")
KEYS = re.compile(r"AIza[0-9A-Za-z_\-]{30,}|gsk_[A-Za-z0-9]{20,}|csk-[A-Za-z0-9]{20,}|sk-[A-Za-z0-9\-]{20,}|hf_[A-Za-z0-9]{20,}")
leaks = []
for f in ROOT.rglob("*"):
    if f.is_file() and f.suffix in {".py", ".js", ".html", ".json", ".md", ".yaml", ".yml", ".example", ".env"} \
       and not any(x in f.parts for x in (".git", "node_modules", ".idea", "__pycache__")):
        if f.name == ".env" or KEYS.search(f.read_text(encoding="utf-8", errors="ignore")):
            leaks.append(str(f.relative_to(ROOT)))
rec("FAIL" if leaks else "PASS", "no API keys in repo files", ", ".join(leaks))

# 3. Safety: models must never reach a shell ------------------------------------
DANGER = re.compile(r"\b(subprocess|os\.system|os\.popen|shell\s*=\s*True|eval\(|exec\(|__import__|pickle\.loads)")
hits = []
for f in py_files("backend"):
    for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        if DANGER.search(line) and not line.strip().startswith("#"):
            hits.append(f"{f.relative_to(ROOT)}:{i}")
rec("FAIL" if hits else "PASS", "no shell/eval/exec in backend", "; ".join(hits[:8]))
reg = read("backend/core/registry.py")
rec("PASS" if re.search(r"effect", reg, re.I) else "FAIL", "registry has effect labels")
rec("PASS" if re.search(r"resolve\(\)|is_relative_to|\.\.", reg + read("backend/core/executor.py")) else "WARN",
    "sandbox path-escape protection present", "look for resolve()/is_relative_to in file actions")

# 4. Architecture invariants -----------------------------------------------------
main, ens, rou = read("backend/main.py"), read("backend/planner/ensemble.py"), read("backend/gateway/router.py")
prov = read("backend/gateway/providers.py").lower()
n_prov = sum(p in prov for p in ["gemini", "groq", "cerebras", "mistral", "openrouter", "ollama"])
rec("PASS" if n_prov >= 2 else "FAIL", f"{n_prov} provider adapters found (need >= 2 different)")
rec("PASS" if re.search(r"except|fallback|failover|next_provider", rou, re.I) else "FAIL", "router has failover logic")
rec("PASS" if re.search(r"Thread|asyncio|gather|concurrent", ens) else "WARN", "planners run in parallel")
rec("PASS" if "manifest" in (ens + main).lower() else "FAIL", "planner uses workspace manifest (not file contents)")
rec("PASS" if re.search(r"verif", main, re.I) else "FAIL", "verifier wired into the API flow")
rec("PASS" if re.search(r"dry", main, re.I) else "FAIL", "dry run exposed by the API")
rec("PASS" if re.search(r"StreamingResponse|EventSource|text/event-stream", main) else "WARN", "live events (SSE) present")
rec("PASS" if "/api/health" in main or "/health" in main else "FAIL", "health endpoint exists")
if "CORSMiddleware" not in main: rec("FAIL", "CORS not configured", "Cloudflare frontend will be blocked")
elif re.search(r'allow_origins\s*=\s*\[\s*"\*"', main): rec("WARN", "CORS allows * (tighten before submitting)")
else: rec("PASS", "CORS restricted to specific origins")
for tag in ["max_steps", "MAX_STEPS", "timeout"]:
    pass
rec("PASS" if re.search(r"max_steps|MAX_STEPS|len\(.*steps", read("backend/core/verifier.py"), re.I) else "WARN", "verifier limits plan size")
rec("PASS" if re.search(r"retr", read("backend/core/executor.py"), re.I) and re.search(r"fallback", read("backend/core/executor.py"), re.I)
    else "WARN", "executor supports retries and fallbacks")

# 5. Env var consistency ---------------------------------------------------------
env_ex = set(re.findall(r"^([A-Z][A-Z0-9_]+)=", read(".env.example"), re.M))
used = set(re.findall(r'(?:getenv|environ(?:\.get)?)\(?\[?\s*["\']([A-Z][A-Z0-9_]+)["\']', "\n".join(f.read_text(errors="ignore") for f in py_files("backend"))))
missing = sorted(used - env_ex)
rec("PASS" if not missing else "WARN", ".env.example lists every env var the code reads", ", ".join(missing))

# 6. Frontend + Render ----------------------------------------------------------------
cfg = read("frontend/config.js")
rec("PASS" if re.search(r"https?://|localhost", cfg) else "WARN", "frontend/config.js defines the backend URL")
rec("PASS" if "/api/" in read("frontend/app.js") else "WARN", "app.js calls /api/ routes")
ry = read("render.yaml")
if ry:
    bad_root = re.search(r"rootDir:\s*backend", ry)
    good_cmd = re.search(r"uvicorn\s+backend\.main:app", ry)
    rec("FAIL" if bad_root and good_cmd else "PASS" if good_cmd else "WARN", "render.yaml start command / rootDir consistent",
        "rootDir: backend breaks 'backend.' imports; deploy from repo root" if bad_root else "")
    rec("PASS" if "$PORT" in ry or "PORT" in ry else "WARN", "render.yaml binds to $PORT")

# 7. Import test -------------------------------------------------------------------
try:
    importlib.import_module("backend.main"); rec("PASS", "backend.main imports cleanly")
except Exception as e:
    rec("FAIL", "backend.main failed to import", f"{type(e).__name__}: {e}")

# 8. Live checks ----------------------------------------------------------------------
if "--url" in sys.argv:
    base = sys.argv[sys.argv.index("--url") + 1].rstrip("/")
    def get(path, headers=None):
        t = time.time()
        with urllib.request.urlopen(urllib.request.Request(base + path, headers=headers or {}), timeout=70) as r:
            return r.status, dict(r.headers), r.read().decode(), round(time.time() - t, 2)
    try:
        s, h, b, dt = get("/api/health"); rec("PASS" if s == 200 else "FAIL", f"GET /api/health ({dt}s)", b[:120])
        s, h, b, dt = get("/openapi.json"); paths = sorted(json.loads(b)["paths"])
        rec("PASS", "routes exposed", ", ".join(paths))
        for want in ["plan", "run", "dry"]:
            rec("PASS" if any(want in p for p in paths) else "FAIL", f"a '{want}' route exists")
        s, h, b, dt = get("/api/health", {"Origin": "https://example-frontend.pages.dev"})
        rec("PASS" if h.get("access-control-allow-origin") else "WARN", "CORS header returned for a foreign origin")
    except Exception as e:
        rec("FAIL", "live check", f"{type(e).__name__}: {e}")

# Report ------------------------------------------------------------------------------------
icon = {"PASS": "[ ok ]", "WARN": "[warn]", "FAIL": "[FAIL]"}
for lvl, name, detail in results: print(f"{icon[lvl]} {name}" + (f"  -> {detail}" if detail else ""))
c = {k: sum(1 for r in results if r[0] == k) for k in icon}
print(f"\n{c['PASS']} passed, {c['WARN']} warnings, {c['FAIL']} failures")
sys.exit(1 if c["FAIL"] else 0)
