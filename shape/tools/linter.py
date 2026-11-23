"""
Tool: Linter
Runs pyflakes static analysis on a code snippet and returns diagnostics.
Used when SHAPE wants to catch errors before executing code.

Group 3 — ITAI2376-14562
Members: Cherluk Sumdin, Olubukola Kukoyi, Taki Eddine Boubekri, Michael Rivas
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from langchain_core.tools import Tool


class LinterTool:
    """
    Runs pyflakes on a Python code snippet and returns lint diagnostics.

    The agent uses this BEFORE code_executor to catch obvious errors
    (undefined names, unused imports) without spending execution time.
    """

    name = "linter"
    description = (
        "Runs static analysis (pyflakes) on a Python code snippet and "
        "returns a list of warnings and errors. Use this BEFORE running code "
        "to catch syntax issues early. Input is Python source code as a string."
    )

    def __init__(self, config: dict[str, Any]) -> None:  # noqa: ARG002
        pass

    def _run(self, code: str) -> str:
        if not code.strip():
            return "[Linter] Empty code — nothing to lint."

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as tmp:
            tmp.write(code)
            tmp_path = Path(tmp.name)

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pyflakes", str(tmp_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # strip the temp path from output for readability
            output = (result.stdout + result.stderr).replace(str(tmp_path), "<code>")
            return output.strip() if output.strip() else "[Linter] No issues found."
        except FileNotFoundError:
            return "[Linter] pyflakes not installed. Run: pip install pyflakes"
        except Exception as exc:  # noqa: BLE001
            return f"[Linter] Error: {exc}"
        finally:
            tmp_path.unlink(missing_ok=True)

    def as_tool(self) -> Tool:
        return Tool(
            name=self.name,
            func=self._run,
            description=self.description,
        )
