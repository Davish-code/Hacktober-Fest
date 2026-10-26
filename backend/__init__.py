import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent
for _p in [_BACKEND_DIR, _BACKEND_DIR / "core", _BACKEND_DIR / "gateway", _BACKEND_DIR / "planner"]:
    _p_str = str(_p)
    if _p_str not in sys.path:
        sys.path.insert(0, _p_str)
