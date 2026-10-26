import os
import time
import uuid
import shutil
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
import pandas as pd
from registry import ActionRegistry
from ledger import ExecutionLedger
from healer import PlanHealer
from manifest import WorkspaceManifest
from actions import (
    action_read_file,
    action_filter_rows,
    action_summarize_text,
    action_write_file,
    action_notify,
    action_draft_email,
    action_send_live_email,
    action_send_whatsapp,
    action_read_google_sheet,
    action_send_gmail,
    action_create_calendar_event,
    action_upload_to_drive,
)

ALLOWED_EXTENSIONS = {".csv", ".txt", ".md", ".json"}


class PlanExecutor:
    """
    Executes validated plans deterministically against the workspace sandbox.
    Supports session isolation, step retries, fallbacks, conditions, on_failure policies,
    and event logging.
    """

    ALLOWED_EXTENSIONS = ALLOWED_EXTENSIONS

    def __init__(
        self,
        workspace_path: Path,
        ledger: Optional[ExecutionLedger] = None,
        seed_path: Optional[Path] = None,
        runs_dir: Optional[Path] = None,
        isolate_sessions: bool = True,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.base_workspace_path = Path(workspace_path)
        self.seed_path = Path(seed_path) if seed_path else (self.base_workspace_path.parent / "workspace_seed")
        self.runs_dir = Path(runs_dir) if runs_dir else (self.base_workspace_path.parent / "workspace_runs")
        self.isolate_sessions = isolate_sessions
        self.workspace_path = self.base_workspace_path
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        self.ledger = ledger or ExecutionLedger(self.workspace_path / "ledger.json")
        self.manifest = WorkspaceManifest(self.workspace_path)
        self.healer = PlanHealer(self.manifest)
        self.intermediate_states: Dict[int, pd.DataFrame] = {}
        self.intermediate_outputs: Dict[int, Any] = {}
        self.step_outputs: Dict[int, Any] = {}
        self.latest_output: Optional[Any] = None
        self.run_log: List[Dict[str, Any]] = []
        self.event_callback = event_callback

    @classmethod
    def cleanup_old_runs(cls, runs_dir: Path, max_age_seconds: int = 3600) -> int:
        """
        Removes run workspace copies older than max_age_seconds (default 1 hour).
        """
        runs_dir = Path(runs_dir)
        cleaned = 0
        if not runs_dir.exists():
            return cleaned

        now = time.time()
        for item in runs_dir.iterdir():
            if item.is_dir() and item.name.startswith("run_"):
                try:
                    if now - item.stat().st_mtime > max_age_seconds:
                        shutil.rmtree(item, ignore_errors=True)
                        cleaned += 1
                except Exception:
                    pass
        return cleaned

    def resolve_safe_path(self, filename: str) -> Path:
        """
        Resolves a filename against the active workspace directory.
        Rejects paths resolving outside the workspace sandbox (absolute paths, '..', symlinks).
        Enforces allowed extensions (.csv, .txt, .md, .json).
        """
        if not filename or not isinstance(filename, str):
            raise ValueError("Sandbox error: Path must be a non-empty string.")

        ws_resolved = self.workspace_path.resolve()
        target = (ws_resolved / filename).resolve()

        # Enforce file extension whitelist
        if target.suffix.lower() not in self.ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Sandbox error: File extension '{target.suffix}' is forbidden. "
                f"Allowed extensions are: {', '.join(sorted(self.ALLOWED_EXTENSIONS))}."
            )

        # Enforce path containment within workspace
        try:
            is_rel = target.is_relative_to(ws_resolved)
        except AttributeError:
            try:
                target.relative_to(ws_resolved)
                is_rel = True
            except ValueError:
                is_rel = False

        if not is_rel or target == ws_resolved:
            raise ValueError(
                f"Sandbox error: Path '{filename}' resolves outside the allowed workspace sandbox '{ws_resolved}'."
            )

        return target

    # Alias for convenience
    resolve_path = resolve_safe_path

    def _resolve_ref(self, ref: Any) -> Any:
        """
        Resolves a reference identifier against previous step outputs and state.
        """
        if not isinstance(ref, str):
            return ref

        if "." in ref:
            parts = ref.split(".")
            step_part = parts[0].replace("step_", "")
            if step_part.isdigit():
                step_idx = int(step_part)
                if step_idx in self.step_outputs:
                    curr = self.step_outputs[step_idx]
                    for p in parts[1:]:
                        if p == "output" and isinstance(curr, dict) and "output" in curr:
                            curr = curr["output"]
                        elif isinstance(curr, dict) and p in curr:
                            curr = curr[p]
                        else:
                            curr = None
                            break
                    return curr
            return None

        # Check latest output
        if self.latest_output and isinstance(self.latest_output, dict) and ref in self.latest_output:
            return self.latest_output[ref]

        # Search step outputs backwards
        for s_id in reversed(list(self.step_outputs.keys())):
            s_out = self.step_outputs[s_id]
            if isinstance(s_out, dict):
                if ref in s_out:
                    return s_out[ref]
                if "output" in s_out and isinstance(s_out["output"], dict) and ref in s_out["output"]:
                    return s_out["output"][ref]

        # Check dataframe row count shortcut
        if ref in ("rows", "remaining_rows", "row_count") and self.intermediate_states:
            last_key = list(self.intermediate_states.keys())[-1]
            return len(self.intermediate_states[last_key])

        return None

    def _resolve_row_list(self, val: Any) -> List[Dict[str, Any]]:
        """
        Resolves a row list from a raw list of dicts, or step references (step_id, 'step_1', etc.).
        """
        if isinstance(val, list):
            return val
        if isinstance(val, int):
            if val in self.intermediate_states:
                return self.intermediate_states[val].to_dict(orient="records")
            if val in self.step_outputs:
                out = self.step_outputs[val]
                if isinstance(out, dict) and "rows" in out and isinstance(out["rows"], list):
                    return out["rows"]
                if isinstance(out, list):
                    return out
        if isinstance(val, str):
            if val in self.intermediate_states:
                return self.intermediate_states[val].to_dict(orient="records")
            clean_key = val.replace("step_", "").split(".")[0]
            if clean_key.isdigit():
                step_idx = int(clean_key)
                if step_idx in self.intermediate_states:
                    return self.intermediate_states[step_idx].to_dict(orient="records")
                if step_idx in self.step_outputs:
                    out = self.step_outputs[step_idx]
                    if isinstance(out, dict) and "rows" in out and isinstance(out["rows"], list):
                        return out["rows"]
                    if isinstance(out, list):
                        return out
            ref_val = self._resolve_ref(val)
            if isinstance(ref_val, list):
                return ref_val
            if isinstance(ref_val, dict) and "rows" in ref_val and isinstance(ref_val["rows"], list):
                return ref_val["rows"]

        if self.intermediate_states:
            last_key = list(self.intermediate_states.keys())[-1]
            return self.intermediate_states[last_key].to_dict(orient="records")

        return []

    def _evaluate_condition(self, condition: Any) -> bool:
        """
        Evaluates step condition 'if': ref/op/value.
        """
        if not condition or not isinstance(condition, dict):
            return True

        ref = condition.get("ref")
        op = condition.get("op") or condition.get("operator", "==")
        expected = condition.get("value")

        if ref is None:
            return True

        actual = self._resolve_ref(ref)

        try:
            if op in ("==", "eq"):
                return str(actual) == str(expected) or actual == expected
            elif op in ("!=", "neq"):
                return str(actual) != str(expected) and actual != expected
            elif op in (">", "gt"):
                return float(actual) > float(expected)
            elif op in ("<", "lt"):
                return float(actual) < float(expected)
            elif op in (">=", "gte"):
                return float(actual) >= float(expected)
            elif op in ("<=", "lte"):
                return float(actual) <= float(expected)
            elif op in ("contains", "in"):
                return str(expected).lower() in str(actual).lower()
            elif op in ("is", "true"):
                return bool(actual) is True
            elif op in ("is_not", "false"):
                return bool(actual) is False
            else:
                return str(actual) == str(expected)
        except Exception:
            return False

    def _log_event(self, run_id: str, step_id: Any, status: str, detail: str) -> Dict[str, Any]:
        """
        Logs an execution event with timestamp, step_id, status, and detail.
        Statuses: started, ok, retry, fallback, skipped, failed, not_run.
        """
        event = {
            "timestamp": time.time(),
            "iso_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "run_id": run_id,
            "step_id": step_id,
            "status": status,
            "detail": detail
        }
        self.run_log.append(event)
        if self.event_callback:
            try:
                self.event_callback(event)
            except Exception:
                pass
        return event

    def execute(
        self,
        plan: Dict[str, Any],
        max_retries: int = 1,
        run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        run_id = run_id or str(uuid.uuid4())
        self.run_log = []
        self.intermediate_states = {}
        self.intermediate_outputs = {}
        self.step_outputs = {}
        self.latest_output = None

        # Session isolation: work on a temporary copy
        if self.isolate_sessions:
            run_workspace = self.runs_dir / f"run_{run_id}"
            run_workspace.mkdir(parents=True, exist_ok=True)
            source_dir = self.base_workspace_path if (self.base_workspace_path.exists() and any(self.base_workspace_path.iterdir())) else self.seed_path
            if source_dir and source_dir.exists():
                for item in source_dir.iterdir():
                    if item.is_file():
                        shutil.copy2(item, run_workspace / item.name)
                    elif item.is_dir():
                        shutil.copytree(item, run_workspace / item.name, dirs_exist_ok=True)
            self.workspace_path = run_workspace
            self.manifest = WorkspaceManifest(self.workspace_path)
            self.healer = PlanHealer(self.manifest)

        steps = plan.get("steps", [])
        step_results = []
        overall_success = True

        for idx, step in enumerate(steps):
            step_id = step.get("step_id", idx + 1)
            action = step.get("action")
            params = step.get("params", {})
            condition = step.get("if")
            retries = min(max(int(step.get("retries", max_retries if "retries" not in step else 0)), 0), 3)
            fallback = step.get("fallback")
            on_failure = step.get("on_failure", "abort").lower()

            # 1. Evaluate condition
            if condition is not None and not self._evaluate_condition(condition):
                cond_desc = f"{condition.get('ref')} {condition.get('op', '==')} {condition.get('value')}"
                self._log_event(run_id, step_id, "skipped", f"Condition '{cond_desc}' evaluated to False")
                step_results.append({
                    "step_id": step_id,
                    "action": action,
                    "status": "SKIPPED",
                    "detail": f"Condition '{cond_desc}' evaluated to False"
                })
                continue

            # 2. Strict whitelist check: prohibit arbitrary execution
            if not ActionRegistry.is_valid_action(action):
                last_error = f"Security Violation: Action '{action}' is not in the allowed ACTION_REGISTRY. Arbitrary shell commands, system calls, and dynamic execution are strictly prohibited."
                tb = f"SecurityException: Prohibited action '{action}' outside whitelisted ACTION_REGISTRY"
                overall_success = False
                heal_info = self.healer.diagnose_and_suggest(step, last_error)
                self._log_event(run_id, step_id, "failed", last_error)
                step_results.append({
                    "step_id": step_id,
                    "action": action,
                    "status": "FAILED",
                    "error": last_error,
                    "traceback": tb,
                    "heal_suggestion": heal_info,
                    "self_repair": heal_info
                })
                # Abort subsequent steps immediately
                for remaining_step in steps[idx + 1:]:
                    rem_id = remaining_step.get("step_id")
                    rem_action = remaining_step.get("action")
                    self._log_event(run_id, rem_id, "not_run", f"Aborted due to security violation in step {step_id}")
                    step_results.append({
                        "step_id": rem_id,
                        "action": rem_action,
                        "status": "NOT_RUN",
                        "detail": f"Aborted due to security violation in step {step_id}"
                    })
                break

            # 3. Start step execution
            self._log_event(run_id, step_id, "started", f"Executing action '{action}'")

            attempt = 0
            success = False
            last_error = ""
            last_traceback = ""
            result_data = None

            # 4. Execution loop with retries & short backoff
            while attempt <= retries and not success:
                try:
                    result_data = self._execute_step(action, params)
                    success = True
                    self.intermediate_outputs[step_id] = result_data
                    self.step_outputs[step_id] = result_data
                    self.latest_output = result_data
                    self._log_event(run_id, step_id, "ok", f"Action '{action}' succeeded")
                    step_results.append({
                        "step_id": step_id,
                        "action": action,
                        "status": "SUCCESS",
                        "output": result_data
                    })
                except Exception as e:
                    last_error = str(e)
                    last_traceback = traceback.format_exc()
                    if attempt < retries:
                        attempt += 1
                        backoff = 0.05 * (2 ** (attempt - 1))
                        self._log_event(
                            run_id,
                            step_id,
                            "retry",
                            f"Attempt {attempt} failed: {last_error}. Retrying in {backoff:.2f}s"
                        )
                        time.sleep(backoff)
                    else:
                        break

            # 5. Fallback execution if primary failed after retries
            if not success and fallback and isinstance(fallback, dict) and "action" in fallback:
                fb_action = fallback.get("action")
                fb_params = fallback.get("params", {})
                self._log_event(
                    run_id,
                    step_id,
                    "fallback",
                    f"Action '{action}' failed after retries ({last_error}). Attempting fallback action '{fb_action}'"
                )
                try:
                    fb_result_data = self._execute_step(fb_action, fb_params)
                    success = True
                    self.intermediate_outputs[step_id] = fb_result_data
                    self.step_outputs[step_id] = fb_result_data
                    self.latest_output = fb_result_data
                    self._log_event(run_id, step_id, "ok", f"Fallback action '{fb_action}' succeeded")
                    step_results.append({
                        "step_id": step_id,
                        "action": action,
                        "status": "SUCCESS",
                        "output": fb_result_data,
                        "fallback_used": fb_action
                    })
                except Exception as fb_err:
                    last_error = f"Primary failed: {last_error}; Fallback '{fb_action}' failed: {str(fb_err)}"
                    last_traceback = traceback.format_exc()

            # 6. Handle failure
            if not success:
                overall_success = False
                heal_info = self.healer.diagnose_and_suggest(step, last_error)
                self._log_event(run_id, step_id, "failed", f"Step failed: {last_error}")
                step_results.append({
                    "step_id": step_id,
                    "action": action,
                    "status": "FAILED",
                    "error": last_error,
                    "traceback": last_traceback,
                    "heal_suggestion": heal_info,
                    "self_repair": heal_info
                })

                if on_failure == "continue":
                    continue
                else:
                    # Abort: Mark subsequent steps as not_run
                    for remaining_step in steps[idx + 1:]:
                        rem_id = remaining_step.get("step_id")
                        rem_action = remaining_step.get("action")
                        self._log_event(
                            run_id,
                            rem_id,
                            "not_run",
                            f"Aborted due to failure in step {step_id}"
                        )
                        step_results.append({
                            "step_id": rem_id,
                            "action": rem_action,
                            "status": "NOT_RUN",
                            "detail": f"Aborted due to failure in step {step_id}"
                        })
                    break

        if overall_success and self.isolate_sessions and self.workspace_path != self.base_workspace_path:
            # Sync generated/modified artifacts back to base workspace
            for item in self.workspace_path.iterdir():
                if item.is_file() and item.name != "ledger.json":
                    dest = self.base_workspace_path / item.name
                    shutil.copy2(item, dest)

        self.ledger.record_run(run_id, plan, step_results, overall_success, run_log=self.run_log)

        return {
            "run_id": run_id,
            "success": overall_success,
            "steps": step_results,
            "run_log": self.run_log
        }

    def _execute_step(self, action: str, params: Dict[str, Any]) -> Any:
        act = action.strip()
        act_lower = act.lower()
        step_id = params.get("step_id", len(self.intermediate_states) + 1)

        # ----------------------------------------------------------------------
        # Multi-Modal Whitelisted Action Handlers
        # ----------------------------------------------------------------------
        if act_lower == "read_file":
            target_path = params.get("path") or params.get("file")
            if not target_path:
                raise ValueError("read_file requires 'path' parameter.")
            res = action_read_file(self.workspace_path, path=target_path, limit=params.get("limit"))
            if res.get("format") == "csv" and "rows" in res:
                self.intermediate_states[step_id] = pd.DataFrame(res["rows"])
            return res

        elif act_lower in ("write_file", "export_csv") or act == "EXPORT_CSV":
            target_path = params.get("path") or params.get("file") or params.get("output_file")
            if not target_path:
                raise ValueError("write_file requires 'path' parameter.")
            content = params.get("content")
            if content is None:
                src_step = params.get("source_step")
                if src_step is not None and src_step in self.intermediate_states:
                    content = self.intermediate_states[src_step].to_dict(orient="records")
                elif src_step is not None and src_step in self.intermediate_outputs:
                    content = self.intermediate_outputs[src_step]
                elif self.intermediate_states:
                    last_k = list(self.intermediate_states.keys())[-1]
                    content = self.intermediate_states[last_k].to_dict(orient="records")
                elif self.latest_output is not None:
                    content = self.latest_output
                else:
                    content = ""
            if isinstance(content, dict) and "rows" in content and isinstance(content["rows"], list):
                content = content["rows"]
            return action_write_file(self.workspace_path, path=target_path, content=content)

        elif act_lower == "summarize_text":
            text_val = params.get("text")
            data_val = None
            if not text_val:
                if "file" in params or "path" in params:
                    file_p = self.resolve_safe_path(params.get("file") or params.get("path"))
                    with open(file_p, "r", encoding="utf-8") as f:
                        text_val = f.read()
                elif "source_step" in params:
                    src_out = self.intermediate_outputs.get(params["source_step"])
                    if isinstance(src_out, str):
                        text_val = src_out
                    elif isinstance(src_out, dict):
                        text_val = str(src_out.get("content") or src_out.get("summary") or src_out)
                    elif params["source_step"] in self.intermediate_states:
                        df_s = self.intermediate_states[params["source_step"]]
                        data_val = df_s.to_dict(orient="records")
                elif self.latest_output is not None:
                    if isinstance(self.latest_output, str):
                        text_val = self.latest_output
                    elif isinstance(self.latest_output, dict):
                        text_val = str(self.latest_output.get("content") or self.latest_output.get("summary") or self.latest_output)
            return action_summarize_text(text=text_val, data=data_val, max_sentences=params.get("max_sentences", 3))

        elif act_lower == "notify":
            return action_notify(message=params.get("message", "Workflow step completed."), level=params.get("level", "info"))

        elif act_lower == "draft_email":
            return action_draft_email(
                to=params.get("to", ""),
                subject=params.get("subject", ""),
                body=params.get("body", ""),
                workspace_path=self.workspace_path
            )

        elif act_lower == "send_live_email":
            return action_send_live_email(
                to=params.get("to", ""),
                subject=params.get("subject", ""),
                body=params.get("body", ""),
                from_email=params.get("from_email")
            )

        elif act_lower == "send_whatsapp":
            return action_send_whatsapp(
                to=params.get("to", ""),
                body=params.get("body") or params.get("message", "")
            )

        elif act_lower == "read_google_sheet":
            return action_read_google_sheet(
                spreadsheet_id=params.get("spreadsheet_id", ""),
                range=params.get("range", "")
            )

        elif act_lower == "send_gmail":
            return action_send_gmail(
                to=params.get("to", ""),
                subject=params.get("subject", ""),
                body=params.get("body", "")
            )

        elif act_lower == "create_calendar_event":
            return action_create_calendar_event(
                summary=params.get("summary") or params.get("title", ""),
                start_time=params.get("start_time", ""),
                end_time=params.get("end_time", ""),
                description=params.get("description")
            )

        elif act_lower == "upload_to_drive":
            file_p = params.get("file_path") or params.get("file", "")
            return action_upload_to_drive(
                workspace_path=self.workspace_path,
                file_path=file_p,
                folder_id=params.get("folder_id")
            )

        # ----------------------------------------------------------------------
        # Tabular / Structured Data Pipeline
        # ----------------------------------------------------------------------
        # Load source data if source_step or file is specified
        source_df: Optional[pd.DataFrame] = None
        if "source_step" in params and params["source_step"] in self.intermediate_states:
            source_df = self.intermediate_states[params["source_step"]].copy()
        elif "file" in params or "path" in params:
            file_name = params.get("file") or params.get("path")
            file_path = self.resolve_safe_path(file_name)
            if not file_path.exists():
                raise FileNotFoundError(f"File '{file_name}' not found in workspace.")
            limit = params.get("limit")
            source_df = pd.read_csv(file_path, nrows=limit if limit else None)
        elif self.intermediate_states:
            last_k = list(self.intermediate_states.keys())[-1]
            source_df = self.intermediate_states[last_k].copy()

        if act_lower in ("read_csv", "read_file") or act == "READ_CSV":
            file_name = params.get("file") or params.get("path")
            file_path = self.resolve_safe_path(file_name)
            if not file_path.exists():
                raise FileNotFoundError(f"File '{file_name}' not found in workspace.")
            df = pd.read_csv(file_path, nrows=params.get("limit"))
            self.intermediate_states[step_id] = df
            records = df.to_dict(orient="records")
            return {"rows": records, "columns": list(df.columns), "count": len(df), "content": records, "format": "csv", "path": file_name}

        elif act_lower in ("filter_rows", "filter") or act == "FILTER_ROWS":
            if source_df is None and "rows" in params:
                source_df = pd.DataFrame(self._resolve_row_list(params["rows"]))
            if source_df is None:
                raise ValueError("No input dataset available for filter_rows.")
            col = params["column"]
            op = params["operator"]
            val = params["value"]
            if col not in source_df.columns:
                raise KeyError(f"Column '{col}' not in dataset. Available columns: {list(source_df.columns)}")

            if op in ("==", "eq"):
                filtered = source_df[source_df[col].astype(str) == str(val)]
            elif op in ("!=", "neq"):
                filtered = source_df[source_df[col].astype(str) != str(val)]
            elif op in (">", "gt"):
                filtered = source_df[pd.to_numeric(source_df[col], errors='coerce') > float(val)]
            elif op in ("<", "lt"):
                filtered = source_df[pd.to_numeric(source_df[col], errors='coerce') < float(val)]
            elif op in (">=", "gte"):
                filtered = source_df[pd.to_numeric(source_df[col], errors='coerce') >= float(val)]
            elif op in ("<=", "lte"):
                filtered = source_df[pd.to_numeric(source_df[col], errors='coerce') <= float(val)]
            elif op in ("contains", "in"):
                filtered = source_df[source_df[col].astype(str).str.contains(str(val), case=False, na=False)]
            else:
                raise ValueError(f"Unsupported operator '{op}'.")

            step_id = params.get("step_id", len(self.intermediate_states) + 1)
            self.intermediate_states[step_id] = filtered
            records = filtered.to_dict(orient="records")
            return {"remaining_rows": len(filtered), "rows": records, "content": records, "count": len(filtered)}

        elif act_lower in ("select_columns", "select") or act == "SELECT_COLUMNS":
            if source_df is None:
                raise ValueError("No input dataset available for SELECT_COLUMNS.")
            cols = params.get("columns", [])
            selected = source_df[[c for c in cols if c in source_df.columns]]
            step_id = params.get("step_id", len(self.intermediate_states) + 1)
            self.intermediate_states[step_id] = selected
            records = selected.to_dict(orient="records")
            return {"columns_selected": list(selected.columns), "rows": records, "count": len(selected)}

        elif act_lower in ("join_data", "join") or act == "JOIN_DATA":
            left_file = params.get("left_file") or params.get("left")
            right_file = params.get("right_file") or params.get("right")
            left_path = self.resolve_safe_path(left_file)
            right_path = self.resolve_safe_path(right_file)
            if not left_path.exists():
                raise FileNotFoundError(f"Left file '{left_file}' not found in workspace.")
            if not right_path.exists():
                raise FileNotFoundError(f"Right file '{right_file}' not found in workspace.")
            left_df = pd.read_csv(left_path)
            right_df = pd.read_csv(right_path)
            how = params.get("how", "inner")
            left_on = params.get("left_on") or params.get("on")
            right_on = params.get("right_on") or params.get("on")
            joined = pd.merge(left_df, right_df, left_on=left_on, right_on=right_on, how=how)
            step_id = params.get("step_id", len(self.intermediate_states) + 1)
            self.intermediate_states[step_id] = joined
            records = joined.to_dict(orient="records")
            return {"joined_rows": len(joined), "columns": list(joined.columns), "rows": records, "count": len(records)}

        elif action in ("join_rows", "JOIN_ROWS"):
            left_rows = self._resolve_row_list(params["left"])
            right_rows = self._resolve_row_list(params["right"])
            left_key = params["left_key"]
            right_key = params["right_key"]
            how = params.get("how", "inner")
            if how not in ("inner", "left"):
                raise ValueError(f"Unsupported join type '{how}'. Must be 'inner' or 'left'.")

            left_cols = list(left_rows[0].keys()) if left_rows else []
            right_cols = list(right_rows[0].keys()) if right_rows else []

            if left_rows and left_key not in left_cols:
                raise KeyError(f"Unknown key column '{left_key}' in left table. Available columns: {left_cols}")
            if right_rows and right_key not in right_cols:
                raise KeyError(f"Unknown key column '{right_key}' in right table. Available columns: {right_cols}")

            # Suffix overlapping columns in right table with _right (other than keys)
            keys_to_preserve = {right_key}
            if left_key == right_key:
                keys_to_preserve.add(left_key)

            overlapping = set(left_cols).intersection(set(right_cols)) - keys_to_preserve
            renamed_right_rows = []
            for r in right_rows:
                new_r = {}
                for k, v in r.items():
                    if k in overlapping:
                        new_r[f"{k}_right"] = v
                    else:
                        new_r[k] = v
                renamed_right_rows.append(new_r)

            left_df = pd.DataFrame(left_rows)
            right_df = pd.DataFrame(renamed_right_rows)

            if left_df.empty or right_df.empty:
                if how == "left" and not left_df.empty:
                    result_df = left_df
                else:
                    result_df = pd.DataFrame()
            else:
                result_df = pd.merge(
                    left_df,
                    right_df,
                    left_on=left_key,
                    right_on=right_key,
                    how=how
                )

            if len(result_df) > 10000:
                raise ValueError(f"Join resulted in {len(result_df)} rows, exceeding maximum limit of 10,000 rows.")

            result_records = result_df.to_dict(orient="records")
            step_id = params.get("step_id", len(self.intermediate_states) + 1)
            self.intermediate_states[step_id] = result_df
            return {"rows": result_records, "count": len(result_records)}

        elif action == "aggregate" or (action == "AGGREGATE" and "rows" in params):
            rows_data = self._resolve_row_list(params["rows"])
            metric = params.get("metric", "").lower()
            group_by = params.get("group_by")
            field = params.get("field")
            output_name = params.get("output_name", "value")

            if metric not in ("sum", "count", "avg", "min", "max"):
                raise ValueError(f"Invalid metric '{metric}'. Allowed metrics are: 'sum', 'count', 'avg', 'min', 'max'.")

            if metric != "count" and not field:
                raise ValueError("Parameter 'field' is required when metric is not 'count'.")

            def safe_to_numeric(val: Any) -> float:
                if isinstance(val, (int, float)):
                    return float(val)
                try:
                    cleaned = str(val).strip()
                    return float(cleaned)
                except (ValueError, TypeError):
                    raise ValueError(f"Cannot aggregate non-numeric value '{val}' in field '{field}' using metric '{metric}'.")

            if not rows_data:
                agg_df = pd.DataFrame()
                step_id = params.get("step_id", len(self.intermediate_states) + 1)
                self.intermediate_states[step_id] = agg_df
                return {"rows": [], "count": 0}

            avail_cols = list(rows_data[0].keys())
            if group_by and group_by not in avail_cols:
                raise KeyError(f"Unknown group_by column '{group_by}'. Available columns: {avail_cols}")
            if field and field not in avail_cols and metric != "count":
                raise KeyError(f"Unknown aggregation field '{field}'. Available columns: {avail_cols}")

            if group_by:
                groups: Dict[Any, List[Dict[str, Any]]] = {}
                for r in rows_data:
                    g_val = r[group_by]
                    if g_val not in groups:
                        groups[g_val] = []
                    groups[g_val].append(r)

                agg_rows = []
                for g_val, g_items in groups.items():
                    if metric == "count":
                        computed = len(g_items)
                    else:
                        num_vals = [safe_to_numeric(item[field]) for item in g_items]
                        if metric == "sum":
                            computed = sum(num_vals)
                        elif metric == "avg":
                            computed = sum(num_vals) / len(num_vals) if num_vals else 0.0
                        elif metric == "min":
                            computed = min(num_vals) if num_vals else None
                        elif metric == "max":
                            computed = max(num_vals) if num_vals else None
                    agg_rows.append({group_by: g_val, output_name: computed})
            else:
                if metric == "count":
                    computed = len(rows_data)
                else:
                    num_vals = [safe_to_numeric(item[field]) for item in rows_data]
                    if metric == "sum":
                        computed = sum(num_vals)
                    elif metric == "avg":
                        computed = sum(num_vals) / len(num_vals) if num_vals else 0.0
                    elif metric == "min":
                        computed = min(num_vals) if num_vals else None
                    elif metric == "max":
                        computed = max(num_vals) if num_vals else None
                agg_rows = [{output_name: computed}]

            agg_df = pd.DataFrame(agg_rows)
            step_id = params.get("step_id", len(self.intermediate_states) + 1)
            self.intermediate_states[step_id] = agg_df
            return {"rows": agg_rows, "count": len(agg_rows)}

        elif action == "AGGREGATE":
            if source_df is None:
                raise ValueError("No input dataset available for AGGREGATE.")
            grp = params["group_by"]
            agg_col = params["agg_col"]
            func = params["func"]
            agg_df = source_df.groupby(grp)[agg_col].agg(func).reset_index()
            step_id = params.get("step_id", len(self.intermediate_states) + 1)
            self.intermediate_states[step_id] = agg_df
            return {"groups_count": len(agg_df)}

        elif action == "SORT_ROWS":
            if source_df is None:
                raise ValueError("No input dataset available for SORT_ROWS.")
            col = params["column"]
            asc = params.get("ascending", True)
            sorted_df = source_df.sort_values(by=col, ascending=asc)
            step_id = params.get("step_id", len(self.intermediate_states) + 1)
            self.intermediate_states[step_id] = sorted_df
            return {"sorted_by": col, "ascending": asc}

        elif action == "EXPORT_CSV":
            if source_df is None:
                raise ValueError("No dataset available to export.")
            out_file = params["output_file"]
            target_path = self.resolve_safe_path(out_file)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            source_df.to_csv(target_path, index=False)
            return {"output_file": out_file, "rows_written": len(source_df)}

        elif action == "GENERATE_SUMMARY":
            if source_df is None:
                raise ValueError("No dataset available to summarize.")
            summary = {
                "row_count": int(len(source_df)),
                "columns": list(source_df.columns),
                "null_counts": source_df.isnull().sum().to_dict()
            }
            return summary

        raise ValueError(f"Unknown action '{action}'")
