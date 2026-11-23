"""
Tool: FileManager
Read and write project files in the workspace directory.
Gives SHAPE persistent code storage across sessions on the Pi's SD card.

Group 3 — ITAI2376-14562
Members: Cherluk Sumdin, Olubukola Kukoyi, Taki Eddine Boubekri, Michael Rivas
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.tools import Tool


class FileManagerTool:
    """
    Read / write files inside the designated workspace directory.

    Security model
    --------------
    All paths are resolved relative to workspace_dir and must stay within it
    (path-traversal protection). The agent cannot access arbitrary filesystem paths.

    Input format (JSON string)
    --------------------------
    Read:  {"action": "read",  "path": "src/hello.py"}
    Write: {"action": "write", "path": "src/hello.py", "content": "print('hi')"}
    List:  {"action": "list",  "path": "src"}
    """

    name = "file_manager"
    description = (
        "Read, write, or list files in the project workspace. "
        "Input must be a JSON string with keys: "
        '"action" (read|write|list), "path" (relative), '
        'and optionally "content" for write. '
        "Example: {\"action\": \"read\", \"path\": \"src/main.py\"}"
    )

    def __init__(self, config: dict[str, Any]) -> None:
        self.workspace = Path(config.get("workspace_dir", "workspace")).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, rel_path: str) -> Path | None:
        """Resolve path and reject anything that escapes workspace_dir."""
        target = (self.workspace / rel_path).resolve()
        if not str(target).startswith(str(self.workspace)):
            return None
        return target

    def _run(self, raw: str) -> str:
        # Parse JSON input
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return "[FileManager] Input must be valid JSON."

        action = data.get("action", "").lower()
        rel = data.get("path", "")

        target = self._safe_path(rel)
        if target is None:
            return "[FileManager] Path traversal detected — request denied."

        if action == "read":
            if not target.exists():
                return f"[FileManager] File not found: {rel}"
            try:
                return target.read_text(encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                return f"[FileManager] Read error: {exc}"

        elif action == "write":
            content = data.get("content", "")
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                return f"[FileManager] Written {len(content)} bytes to {rel}."
            except Exception as exc:  # noqa: BLE001
                return f"[FileManager] Write error: {exc}"

        elif action == "list":
            if not target.exists():
                return f"[FileManager] Directory not found: {rel}"
            entries = sorted(str(p.relative_to(self.workspace)) for p in target.iterdir())
            return "\n".join(entries) if entries else "[FileManager] Directory is empty."

        else:
            return f"[FileManager] Unknown action '{action}'. Use read, write, or list."

    def as_tool(self) -> Tool:
        return Tool(
            name=self.name,
            func=self._run,
            description=self.description,
        )
