from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel


class ActionEffect(str, Enum):
    READ = "READ"
    TRANSFORM = "TRANSFORM"
    WRITE = "WRITE"
    ANALYZE = "ANALYZE"
    SANDBOXED = "SANDBOXED"
    GATED_WRITE = "GATED_WRITE"
    GATED_READ = "GATED_READ"


class ActionDefinition(BaseModel):
    name: str
    effect: ActionEffect
    permission: str
    description: str
    required_params: List[str]
    optional_params: List[str] = []
    outputs: List[str] = []


ACTION_REGISTRY: Dict[str, ActionDefinition] = {
    # --------------------------------------------------------------------------
    # 1. Local Data & File Operations
    # --------------------------------------------------------------------------
    "read_file": ActionDefinition(
        name="read_file",
        effect=ActionEffect.READ,
        permission="read",
        description="Reads a local file (.csv, .txt, .md, .json) safely from the workspace sandbox into memory.",
        required_params=["path"],
        optional_params=["file", "limit"],
        outputs=["content", "rows", "columns", "format", "count"]
    ),
    "filter_rows": ActionDefinition(
        name="filter_rows",
        effect=ActionEffect.TRANSFORM,
        permission="transform",
        description="Filters dataset rows based on a column condition (==, !=, >, <, >=, <=, contains).",
        required_params=["column", "operator", "value"],
        optional_params=["file", "path", "source_step", "rows"],
        outputs=["remaining_rows", "rows", "count"]
    ),
    "summarize_text": ActionDefinition(
        name="summarize_text",
        effect=ActionEffect.ANALYZE,
        permission="analyze",
        description="Generates an extractive statistical summary (length, word count, sentences) of text or dataset.",
        required_params=[],
        optional_params=["text", "file", "path", "source_step", "max_sentences"],
        outputs=["summary", "word_count", "char_count"]
    ),
    "write_file": ActionDefinition(
        name="write_file",
        effect=ActionEffect.WRITE,
        permission="write",
        description="Saves text, JSON, or tabular content safely to a designated file inside the workspace sandbox.",
        required_params=["path"],
        optional_params=["content", "source_step", "file", "output_file"],
        outputs=["path", "bytes_written", "status"]
    ),
    "notify": ActionDefinition(
        name="notify",
        effect=ActionEffect.READ,
        permission="read",
        description="Dispatches a run trace notification event to the console and audit ledger.",
        required_params=["message"],
        optional_params=["level"],
        outputs=["delivered", "message", "level"]
    ),

    # --------------------------------------------------------------------------
    # 2. Sandboxed Operations
    # --------------------------------------------------------------------------
    "draft_email": ActionDefinition(
        name="draft_email",
        effect=ActionEffect.SANDBOXED,
        permission="sandboxed_write",
        description="Strictly sandboxed email drafting. Saves draft to local sandbox ledger with ZERO network egress.",
        required_params=["to", "subject", "body"],
        optional_params=["cc", "bcc"],
        outputs=["status", "draft_id", "to", "subject", "sandboxed"]
    ),

    # --------------------------------------------------------------------------
    # 3. Live Communications (Gated)
    # --------------------------------------------------------------------------
    "send_live_email": ActionDefinition(
        name="send_live_email",
        effect=ActionEffect.GATED_WRITE,
        permission="gated_write",
        description="Transmits a live email via SMTP. Gated by explicit configuration credentials.",
        required_params=["to", "subject", "body"],
        optional_params=["from_email"],
        outputs=["status", "to", "subject", "gate_status"]
    ),
    "send_whatsapp": ActionDefinition(
        name="send_whatsapp",
        effect=ActionEffect.GATED_WRITE,
        permission="gated_write",
        description="Dispatches a live WhatsApp message via Twilio API. Gated by Twilio credentials.",
        required_params=["to", "body"],
        optional_params=["message"],
        outputs=["status", "to", "gate_status"]
    ),

    # --------------------------------------------------------------------------
    # 4. Google Workspace (Gated)
    # --------------------------------------------------------------------------
    "read_google_sheet": ActionDefinition(
        name="read_google_sheet",
        effect=ActionEffect.GATED_READ,
        permission="gated_read",
        description="Reads spreadsheet data via Google Workspace Sheets API (gated).",
        required_params=["spreadsheet_id", "range"],
        optional_params=[],
        outputs=["status", "rows", "spreadsheet_id", "gate_status"]
    ),
    "send_gmail": ActionDefinition(
        name="send_gmail",
        effect=ActionEffect.GATED_WRITE,
        permission="gated_write",
        description="Sends an email via Google Workspace Gmail API (gated).",
        required_params=["to", "subject", "body"],
        optional_params=[],
        outputs=["status", "to", "subject", "gate_status"]
    ),
    "create_calendar_event": ActionDefinition(
        name="create_calendar_event",
        effect=ActionEffect.GATED_WRITE,
        permission="gated_write",
        description="Creates an event in Google Calendar via Google Calendar API (gated).",
        required_params=["summary", "start_time", "end_time"],
        optional_params=["description", "title"],
        outputs=["status", "event_id", "summary", "gate_status"]
    ),
    "upload_to_drive": ActionDefinition(
        name="upload_to_drive",
        effect=ActionEffect.GATED_WRITE,
        permission="gated_write",
        description="Uploads a sandboxed file to Google Drive via Google Drive API (gated).",
        required_params=["file_path"],
        optional_params=["folder_id", "file"],
        outputs=["status", "file_name", "drive_file_id", "gate_status"]
    ),

    # --------------------------------------------------------------------------
    # 5. Core Tabular & Verifier Pipeline Actions (Legacy / Backward-compatible)
    # --------------------------------------------------------------------------
    "READ_CSV": ActionDefinition(
        name="READ_CSV",
        effect=ActionEffect.READ,
        permission="read",
        description="Reads a CSV file from the workspace sandbox into memory.",
        required_params=["file"],
        optional_params=["limit"],
        outputs=["rows", "columns"]
    ),
    "FILTER_ROWS": ActionDefinition(
        name="FILTER_ROWS",
        effect=ActionEffect.TRANSFORM,
        permission="transform",
        description="Filters rows based on a column condition (==, !=, >, <, contains).",
        required_params=["column", "operator", "value"],
        optional_params=["file", "source_step", "rows"],
        outputs=["remaining_rows"]
    ),
    "SELECT_COLUMNS": ActionDefinition(
        name="SELECT_COLUMNS",
        effect=ActionEffect.TRANSFORM,
        permission="transform",
        description="Selects a subset of columns from a dataset.",
        required_params=["columns"],
        optional_params=["file", "source_step"],
        outputs=["columns_selected", "rows"]
    ),
    "JOIN_DATA": ActionDefinition(
        name="JOIN_DATA",
        effect=ActionEffect.TRANSFORM,
        permission="transform",
        description="Joins two datasets on specified keys (inner, left, right).",
        required_params=["left_file", "right_file", "left_on", "right_on"],
        optional_params=["how"],
        outputs=["joined_rows", "columns"]
    ),
    "AGGREGATE": ActionDefinition(
        name="AGGREGATE",
        effect=ActionEffect.TRANSFORM,
        permission="transform",
        description="Groups data and calculates aggregations (sum, count, mean, min, max).",
        required_params=["group_by", "agg_col", "func"],
        optional_params=["file", "source_step", "rows", "metric", "field", "output_name"],
        outputs=["groups_count"]
    ),
    "SORT_ROWS": ActionDefinition(
        name="SORT_ROWS",
        effect=ActionEffect.TRANSFORM,
        permission="transform",
        description="Sorts dataset rows by column ascending or descending.",
        required_params=["column"],
        optional_params=["ascending", "file", "source_step"],
        outputs=["sorted_by", "ascending"]
    ),
    "EXPORT_CSV": ActionDefinition(
        name="EXPORT_CSV",
        effect=ActionEffect.WRITE,
        permission="write",
        description="Saves a dataset to a specified CSV file in the workspace.",
        required_params=["output_file"],
        optional_params=["source_step", "file"],
        outputs=["output_file", "rows_written"]
    ),
    "GENERATE_SUMMARY": ActionDefinition(
        name="GENERATE_SUMMARY",
        effect=ActionEffect.ANALYZE,
        permission="analyze",
        description="Produces statistical metrics (row count, distinct values, nulls) for dataset.",
        required_params=[],
        optional_params=["file", "source_step"],
        outputs=["row_count", "columns", "null_counts"]
    ),
    "join_rows": ActionDefinition(
        name="join_rows",
        effect=ActionEffect.READ,
        permission="transform",
        description="Joins two row lists on specified key columns with optional left/inner join.",
        required_params=["left", "right", "left_key", "right_key"],
        optional_params=["how"],
        outputs=["rows", "count"]
    ),
    "aggregate": ActionDefinition(
        name="aggregate",
        effect=ActionEffect.READ,
        permission="transform",
        description="Groups rows and computes aggregations (sum, count, avg, min, max).",
        required_params=["rows", "metric"],
        optional_params=["group_by", "field", "output_name"],
        outputs=["rows", "count"]
    ),
}


class ActionRegistry:
    """
    The safe actions registry with strictly bounded semantics and permission labels.
    CRITICAL: Strictly prohibits arbitrary shell commands or dynamic execution.
    Every operation must be mapped to this hardcoded whitelist.
    """

    ACTIONS: Dict[str, ActionDefinition] = ACTION_REGISTRY

    @classmethod
    def get_action(cls, name: str) -> ActionDefinition:
        if name in cls.ACTIONS:
            return cls.ACTIONS[name]
        lower_name = name.lower()
        if lower_name in cls.ACTIONS:
            return cls.ACTIONS[lower_name]
        upper_name = name.upper()
        if upper_name in cls.ACTIONS:
            return cls.ACTIONS[upper_name]
        raise ValueError(
            f"Action '{name}' is not in the allowed safe actions registry. "
            f"Arbitrary commands, system calls, and dynamic execution are strictly prohibited."
        )

    @classmethod
    def is_valid_action(cls, name: str) -> bool:
        if not name or not isinstance(name, str):
            return False
        return (
            name in cls.ACTIONS
            or name.lower() in cls.ACTIONS
            or name.upper() in cls.ACTIONS
        )

    @classmethod
    def get_all_actions(cls) -> Dict[str, ActionDefinition]:
        return cls.ACTIONS

    @classmethod
    def get_actions_list(cls) -> List[Dict[str, Any]]:
        """Returns structured metadata for the GET /api/actions endpoint."""
        seen = set()
        items = []
        # Return standardized lowercase / primary action names first
        for name, act in cls.ACTIONS.items():
            canonical = name.lower()
            if canonical in seen:
                continue
            seen.add(canonical)
            items.append({
                "name": act.name,
                "description": act.description,
                "permission": act.permission,
                "effect": act.effect.value,
                "required_params": act.required_params,
                "optional_params": act.optional_params,
                "outputs": act.outputs
            })
        return items

    @classmethod
    def validate_outputs(cls, name: str, output_data: Any) -> bool:
        action_def = cls.get_action(name)
        if not action_def.outputs:
            return True
        if not isinstance(output_data, dict):
            return False
        return all(out in output_data for out in action_def.outputs)
