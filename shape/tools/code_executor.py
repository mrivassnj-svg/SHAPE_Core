"""
Tool: CodeExecutor
Runs Python code in a subprocess sandbox with a timeout.
Used when SHAPE needs to test or validate generated code.

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


class CodeExecutorTool:
    """
    Executes a Python code snippet in an isolated subprocess.

    Safety constraints
    ------------------
    - Hard timeout (default 10 s) prevents infinite loops.
    - Code runs in a fresh temp file — no access to agent internals.
    - Output is capped at 4 KB to prevent memory flooding on the Pi.
    """

    name = "code_executor"
    description = (
        "Executes a Python code snippet and returns stdout + stderr. "
        "Use this to test whether generated code runs correctly. "
        "Input must be valid Python source code as a plain string."
    )

    def __init__(self, config: dict[str, Any]) -> None:
        self.timeout = config.get("executor_timeout", 10)
        self.max_output = config.get("executor_max_output", 4096)

    def _run(self, code: str) -> str:
        if not code.strip():
            return "[CodeExecutor] Empty code — nothing to run."

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as tmp:
            tmp.write(code)
            tmp_path = Path(tmp.name)

        try:
            result = subprocess.run(
                [sys.executable, str(tmp_path)],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            output = result.stdout + result.stderr
            if len(output) > self.max_output:
                output = output[: self.max_output] + "\n[... output truncated]"
            return output if output.strip() else "[CodeExecutor] No output produced."
        except subprocess.TimeoutExpired:
            return f"[CodeExecutor] Execution timed out after {self.timeout} s."
        except Exception as exc:  # noqa: BLE001
            return f"[CodeExecutor] Error: {exc}"
        finally:
            tmp_path.unlink(missing_ok=True)

    def as_tool(self) -> Tool:
        return Tool(
            name=self.name,
            func=self._run,
            description=self.description,
        )
