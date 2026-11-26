"""
shape.parser — ReAct output parser for SHAPE.

Extracted from agent.py so it can be imported and tested independently.
Notebook 02 demonstrates this module; test_parser.py validates it.

Group 3 — ITAI2376-14562
"""
from __future__ import annotations

import re


def parse_llm_output(text: str) -> dict:
    """
    Parse a CodeLlama text completion into a structured ReAct step.

    Returns one of:
        {"type": "final",  "answer": str}
        {"type": "action", "tool": str, "input": str}

    The three branches in priority order:
    1. Final Answer   — re.search(r"Final Answer\\s*:\\s*(.+)", text, DOTALL)
    2. Action         — re.search(r"Action\\s*:\\s*(.+)", text)
    3. Plain fallback — treat entire text as a final answer

    The fallback (branch 3) handles CodeLlama responses that omit the
    format tags entirely, ensuring the agent never crashes on unexpected output.
    """
    # Branch 1: Final Answer
    fa = re.search(r"Final Answer\s*:\s*(.+)", text, re.DOTALL | re.IGNORECASE)
    if fa:
        return {"type": "final", "answer": fa.group(1).strip()}

    # Branch 2: Action + Action Input
    act = re.search(r"Action\s*:\s*(.+)", text)
    inp = re.search(r"Action Input\s*:\s*(.+)", text, re.DOTALL)
    if act:
        return {
            "type":  "action",
            "tool":  act.group(1).strip(),
            "input": inp.group(1).strip() if inp else "",
        }

    # Branch 3: Graceful fallback
    return {"type": "final", "answer": text.strip()}
