import csv
from pathlib import Path
from typing import Dict, List, Any


class WorkspaceManifest:
    """
    Scans the workspace directory for available datasets.
    Extracts file names, column headers, and column types ONLY (no row data).
    """

    def __init__(self, workspace_path: Path):
        self.workspace_path = Path(workspace_path)

    def scan(self) -> Dict[str, Dict[str, Any]]:
        manifest: Dict[str, Dict[str, Any]] = {}
        if not self.workspace_path.exists():
            return manifest

        for file_path in self.workspace_path.glob("*.csv"):
            file_name = file_path.name
            columns = self._extract_columns(file_path)
            manifest[file_name] = {
                "file_name": file_name,
                "columns": columns,
                "size_bytes": file_path.stat().st_size
            }
        return manifest

    def _extract_columns(self, file_path: Path) -> List[str]:
        try:
            with open(file_path, mode="r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                header = next(reader, [])
                return [col.strip() for col in header if col.strip()]
        except Exception:
            return []

    def get_columns_for_file(self, file_name: str) -> List[str]:
        manifest = self.scan()
        if file_name in manifest:
            return manifest[file_name]["columns"]
        return []
