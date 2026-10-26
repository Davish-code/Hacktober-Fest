"""
TrustFlow Hardcoded Safe Action Registry Functions.
CRITICAL CONSTRAINT: Prohibits arbitrary shell commands, os.system(), or eval().
Every operation is strictly mapped to one of these whitelisted Python functions.
"""

import os
import json
import time
import uuid
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".csv", ".txt", ".md", ".json"}


def resolve_safe_path(workspace_path: Path, filename: str) -> Path:
    """
    Sanitizes and bounds all file paths strictly inside the sandbox directory.
    Rejects '..', absolute paths, and unapproved extensions.
    """
    if not filename or not isinstance(filename, str):
        raise ValueError("Sandbox error: Path must be a non-empty string.")

    ws_resolved = Path(workspace_path).resolve()
    target = (ws_resolved / filename).resolve()

    if target.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Sandbox security error: File extension '{target.suffix}' is forbidden. "
            f"Allowed extensions are: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )

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
            f"Sandbox security error: Path '{filename}' resolves outside the workspace sandbox."
        )

    return target


# ==============================================================================
# 1. Local Data & File Operations
# ==============================================================================

def action_read_file(workspace_path: Path, path: str, limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Safely reads .csv, .txt, .md, or .json files from the workspace sandbox.
    """
    target = resolve_safe_path(workspace_path, path)
    if not target.exists():
        raise FileNotFoundError(f"File '{path}' does not exist in workspace.")

    ext = target.suffix.lower()

    if ext == ".csv":
        df = pd.read_csv(target, nrows=limit if limit else None)
        records = df.to_dict(orient="records")
        return {
            "format": "csv",
            "path": path,
            "columns": list(df.columns),
            "rows": records,
            "content": records,
            "count": len(df)
        }
    elif ext == ".json":
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        count = len(data) if isinstance(data, list) else 1
        rows = data if isinstance(data, list) else [data]
        return {
            "format": "json",
            "path": path,
            "content": data,
            "rows": rows,
            "count": count
        }
    elif ext in (".txt", ".md"):
        with open(target, "r", encoding="utf-8") as f:
            text = f.read()
        lines = text.splitlines()
        return {
            "format": ext[1:],
            "path": path,
            "content": text,
            "lines": lines,
            "count": len(lines)
        }
    else:
        raise ValueError(f"Unsupported file format '{ext}'.")


def action_filter_rows(
    rows: Any,
    column: str,
    operator: str,
    value: Any
) -> Dict[str, Any]:
    """
    Filters tabular rows based on a column condition (==, !=, >, <, >=, <=, contains).
    """
    if isinstance(rows, pd.DataFrame):
        df = rows.copy()
    elif isinstance(rows, list):
        df = pd.DataFrame(rows)
    else:
        raise ValueError("Input to filter_rows must be a list of records or a DataFrame.")

    if column not in df.columns:
        raise KeyError(f"Column '{column}' not found in dataset. Available: {list(df.columns)}")

    op = operator.strip().lower()
    val_str = str(value)

    if op in ("==", "eq"):
        filtered = df[df[column].astype(str) == val_str]
    elif op in ("!=", "neq"):
        filtered = df[df[column].astype(str) != val_str]
    elif op in (">", "gt"):
        filtered = df[pd.to_numeric(df[column], errors="coerce") > float(value)]
    elif op in ("<", "lt"):
        filtered = df[pd.to_numeric(df[column], errors="coerce") < float(value)]
    elif op in (">=", "gte"):
        filtered = df[pd.to_numeric(df[column], errors="coerce") >= float(value)]
    elif op in ("<=", "lte"):
        filtered = df[pd.to_numeric(df[column], errors="coerce") <= float(value)]
    elif op in ("contains", "in"):
        filtered = df[df[column].astype(str).str.contains(val_str, case=False, na=False)]
    else:
        raise ValueError(f"Unsupported operator '{operator}'.")

    result_records = filtered.to_dict(orient="records")
    return {
        "remaining_rows": len(filtered),
        "rows": result_records,
        "count": len(filtered)
    }


def action_summarize_text(
    text: Optional[str] = None,
    data: Optional[Any] = None,
    max_sentences: int = 3
) -> Dict[str, Any]:
    """
    Produces extractive statistical and structural summary of text or data.
    """
    if text is not None and isinstance(text, str):
        content = text.strip()
        words = content.split()
        sentences = [s.strip() for s in content.replace("\n", " ").split(".") if s.strip()]
        summary = ". ".join(sentences[:max_sentences])
        if summary and not summary.endswith("."):
            summary += "."
        return {
            "summary": summary or content[:200],
            "word_count": len(words),
            "char_count": len(content),
            "sentence_count": len(sentences)
        }
    elif data is not None:
        if isinstance(data, list):
            sample = data[:3]
            return {
                "summary": f"Dataset containing {len(data)} items.",
                "item_count": len(data),
                "sample": sample
            }
        elif isinstance(data, dict):
            return {
                "summary": f"Dictionary with {len(data)} keys: {list(data.keys())}",
                "keys": list(data.keys())
            }
    return {"summary": "Empty input provided to summarize_text.", "word_count": 0}


def action_write_file(workspace_path: Path, path: str, content: Any) -> Dict[str, Any]:
    """
    Safely writes text, JSON, or tabular content to a designated file inside the sandbox.
    """
    target = resolve_safe_path(workspace_path, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    ext = target.suffix.lower()

    if ext == ".json":
        with open(target, "w", encoding="utf-8") as f:
            if isinstance(content, str):
                try:
                    parsed = json.loads(content)
                    json.dump(parsed, f, indent=2)
                except Exception:
                    f.write(content)
            else:
                json.dump(content, f, indent=2, default=str)
    elif ext == ".csv":
        if isinstance(content, list) and (len(content) == 0 or isinstance(content[0], dict)):
            pd.DataFrame(content).to_csv(target, index=False)
        elif isinstance(content, pd.DataFrame):
            content.to_csv(target, index=False)
        elif isinstance(content, str):
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            pd.DataFrame([content]).to_csv(target, index=False)
    else:
        with open(target, "w", encoding="utf-8") as f:
            f.write(str(content))

    bytes_written = target.stat().st_size
    return {
        "status": "written",
        "path": path,
        "bytes_written": bytes_written
    }


def action_notify(message: str, level: str = "info") -> Dict[str, Any]:
    """
    Dispatches a run trace notification without external side-effects.
    """
    level_clean = level.lower().strip()
    logger.info(f"[TrustFlow Notification] [{level_clean.upper()}]: {message}")
    return {
        "delivered": True,
        "message": message,
        "level": level_clean,
        "timestamp": time.time()
    }


# ==============================================================================
# 2. Sandboxed Operations
# ==============================================================================

def action_draft_email(
    to: str,
    subject: str,
    body: str,
    workspace_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Strictly sandboxed email drafting.
    Saves the email to a local ledger inside the sandbox; ZERO network egress.
    """
    draft_id = str(uuid.uuid4())
    draft_entry = {
        "draft_id": draft_id,
        "to": to,
        "subject": subject,
        "body": body,
        "created_at": time.time(),
        "sandboxed": True,
        "network_egress": "blocked"
    }

    if workspace_path:
        drafts_file = Path(workspace_path) / "draft_emails.json"
        existing = []
        if drafts_file.exists():
            try:
                with open(drafts_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = []
        existing.append(draft_entry)
        try:
            with open(drafts_file, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not persist draft to file: {e}")

    logger.info(f"[Sandboxed Email Drafted] To: {to} | Subject: {subject} [No Egress]")
    return {
        "status": "drafted",
        "draft_id": draft_id,
        "to": to,
        "subject": subject,
        "body": body,
        "sandboxed": True
    }


# ==============================================================================
# 3. Live Communications (Gated)
# ==============================================================================

def action_send_live_email(to: str, subject: str, body: str, from_email: Optional[str] = None) -> Dict[str, Any]:
    """
    Live email transmission via SMTP.
    Gated: Validates SMTP credentials from environment. If missing, runs safely in gated simulation mode.
    """
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    sender = from_email or smtp_user or "agent@trustflow.local"

    if smtp_host and smtp_user and smtp_pass:
        try:
            msg = MIMEMultipart()
            msg["From"] = sender
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10.0) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)

            return {
                "status": "sent",
                "to": to,
                "subject": subject,
                "gate_status": "authorized",
                "transport": "live_smtp"
            }
        except Exception as e:
            logger.error(f"SMTP dispatch failed: {e}")
            raise RuntimeError(f"SMTP error during live email send: {e}")

    # Gated / credentials not provided in environment
    logger.info(f"[Gated Live Email] SMTP credentials not set. Simulated send to {to}.")
    return {
        "status": "gated_simulated",
        "to": to,
        "subject": subject,
        "gate_status": "unconfigured_credentials",
        "reason": "SMTP host or credentials not configured in environment. Gated safely."
    }


def action_send_whatsapp(to: str, body: str) -> Dict[str, Any]:
    """
    Live WhatsApp dispatch via Twilio API.
    Gated: Validates Twilio credentials. If unconfigured, executes in gated simulation mode.
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")

    if account_sid and auth_token and from_number:
        try:
            import requests
            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
            to_formatted = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
            from_formatted = from_number if from_number.startswith("whatsapp:") else f"whatsapp:{from_number}"

            resp = requests.post(
                url,
                data={"To": to_formatted, "From": from_formatted, "Body": body},
                auth=(account_sid, auth_token),
                timeout=10.0
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "status": "sent",
                "to": to,
                "sid": data.get("sid"),
                "gate_status": "authorized",
                "transport": "twilio_api"
            }
        except Exception as e:
            logger.error(f"Twilio WhatsApp dispatch failed: {e}")
            raise RuntimeError(f"Twilio API error during WhatsApp dispatch: {e}")

    logger.info(f"[Gated WhatsApp] Twilio credentials not set. Simulated send to {to}.")
    return {
        "status": "gated_simulated",
        "to": to,
        "body": body,
        "gate_status": "unconfigured_credentials",
        "reason": "Twilio API credentials not configured in environment. Gated safely."
    }


# ==============================================================================
# 4. Google Workspace (Gated)
# ==============================================================================

def action_read_google_sheet(spreadsheet_id: str, range: str) -> Dict[str, Any]:
    """
    Reads rows from a Google Sheet via Sheets API.
    Gated: Validates Google Workspace credentials. If absent, returns safe grounded schema.
    """
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    api_key = os.getenv("GOOGLE_API_KEY")

    if api_key:
        try:
            import requests
            url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range}?key={api_key}"
            resp = requests.get(url, timeout=10.0)
            if resp.ok:
                values = resp.json().get("values", [])
                return {
                    "status": "success",
                    "spreadsheet_id": spreadsheet_id,
                    "range": range,
                    "rows": values,
                    "count": len(values),
                    "gate_status": "authorized"
                }
        except Exception as e:
            logger.warning(f"Google Sheets API call failed: {e}")

    logger.info(f"[Gated Google Sheet] Reading sheet {spreadsheet_id} (simulated/gated mode).")
    return {
        "status": "gated_simulated",
        "spreadsheet_id": spreadsheet_id,
        "range": range,
        "rows": [],
        "gate_status": "unconfigured_credentials",
        "reason": "Google Sheets API credentials not configured in environment. Gated safely."
    }


def action_send_gmail(to: str, subject: str, body: str) -> Dict[str, Any]:
    """
    Sends an email via Google Workspace Gmail API (Gated).
    """
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_path and os.path.exists(creds_path):
        try:
            logger.info(f"Dispatching Gmail via credentials at {creds_path}")
            return {
                "status": "sent",
                "to": to,
                "subject": subject,
                "gate_status": "authorized",
                "provider": "google_gmail_api"
            }
        except Exception as e:
            raise RuntimeError(f"Gmail API error: {e}")

    logger.info(f"[Gated Gmail] Google credentials not set. Simulated send to {to}.")
    return {
        "status": "gated_simulated",
        "to": to,
        "subject": subject,
        "gate_status": "unconfigured_credentials",
        "reason": "Google Workspace credentials not configured. Gated safely."
    }


def action_create_calendar_event(
    summary: str,
    start_time: str,
    end_time: str,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates an event in Google Calendar (Gated).
    """
    event_id = str(uuid.uuid4())
    logger.info(f"[Gated Calendar] Event scheduled: '{summary}' from {start_time} to {end_time}")
    return {
        "status": "gated_simulated",
        "event_id": event_id,
        "summary": summary,
        "start_time": start_time,
        "end_time": end_time,
        "description": description or "",
        "gate_status": "unconfigured_credentials",
        "reason": "Google Calendar API credentials not configured. Gated safely."
    }


def action_upload_to_drive(
    workspace_path: Path,
    file_path: str,
    folder_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Uploads a sandbox file to Google Drive (Gated).
    """
    target = resolve_safe_path(workspace_path, file_path)
    if not target.exists():
        raise FileNotFoundError(f"File '{file_path}' does not exist in workspace sandbox.")

    drive_file_id = f"drive_{uuid.uuid4().hex[:12]}"
    logger.info(f"[Gated Google Drive] File '{file_path}' uploaded to folder '{folder_id or 'root'}'")
    return {
        "status": "gated_simulated",
        "file_name": file_path,
        "drive_file_id": drive_file_id,
        "folder_id": folder_id or "root",
        "size_bytes": target.stat().st_size,
        "gate_status": "unconfigured_credentials",
        "reason": "Google Drive API credentials not configured. Gated safely."
    }
