"""
SHAPE Safety / InputGuard module
Screens user input for prohibited requests before the agent processes them.

Group 3 — ITAI2376-14562
Members: Cherluk Sumdin, Olubukola Kukoyi, Taki Eddine Boubekri, Michael Rivas
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Pattern library
# ---------------------------------------------------------------------------

# Requests that could harm the host system or violate academic policy
_BLOCKED_PATTERNS: list[tuple[str, str]] = [
    (r"\bos\.system\s*\(", "direct OS system call"),
    (r"\bsubprocess\.Popen\b.*shell\s*=\s*True", "shell=True subprocess"),
    (r"\brm\s+-rf\b", "destructive shell command"),
    (r"\beval\s*\(.*input\b", "eval with user input"),
    (r"\b__import__\s*\(\s*['\"]os['\"]", "dynamic os import"),
    (r"(?i)\b(hack|exploit|malware|ransomware|keylogger)\b", "prohibited security topic"),
    (r"(?i)generate.{0,20}(virus|worm|trojan)", "malware generation request"),
    (r"(?i)how.{0,30}bypass.{0,30}(auth|firewall|security)", "security bypass request"),
]

# Requests outside the coding domain that SHAPE politely declines
_OUT_OF_SCOPE_PATTERNS: list[tuple[str, str]] = [
    (r"(?i)\b(medical|diagnosis|prescription|dosage)\b", "medical advice (out of scope)"),
    (r"(?i)\b(legal advice|sue|lawsuit|attorney)\b", "legal advice (out of scope)"),
    (r"(?i)\bwrite.{0,20}(essay|poem|story)\b", "non-coding creative writing (out of scope)"),
]

_MAX_INPUT_LENGTH = 8000  # characters


class InputGuard:
    """
    Screens input before it reaches the LLM.

    Returns (blocked: bool, reason: str).
    If blocked is True, the agent returns the reason directly without
    calling the LLM — this prevents wasted compute and unsafe outputs.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or {}
        self.max_length = cfg.get("max_input_length", _MAX_INPUT_LENGTH)
        self.extra_blocked = [
            (pat, "user-defined blocked pattern")
            for pat in cfg.get("extra_blocked_patterns", [])
        ]

    def check(self, text: str) -> tuple[bool, str]:
        """
        Returns (True, reason) if the input should be blocked,
        or (False, "") if it is safe to process.
        """
        # 1. Length check
        if len(text) > self.max_length:
            return True, f"Input exceeds maximum length ({self.max_length} chars)."

        # 2. Blocked security / harmful patterns
        for pattern, reason in _BLOCKED_PATTERNS + self.extra_blocked:
            if re.search(pattern, text):
                return True, f"Request contains a prohibited pattern: {reason}."

        # 3. Out-of-scope soft block
        for pattern, reason in _OUT_OF_SCOPE_PATTERNS:
            if re.search(pattern, text):
                return True, (
                    f"SHAPE is a coding agent and cannot help with: {reason}. "
                    "Please ask a programming question."
                )

        return False, ""
