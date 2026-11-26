"""
shape.rewards — RL reward loop (canonical module)

Previously feedback.py. Import from shape.rewards in all new code.
shape.feedback is kept as a compatibility shim.

Notebook 04 demonstrates this module.
Persists user ratings, computes a running policy hint, and improves
the agent's prompt strategy over time (reflection-based RL).

Group 3 — ITAI2376-14562
Members: Cherluk Sumdin, Olubukola Kukoyi, Taki Eddine Boubekri, Michael Rivas
"""

from __future__ import annotations

import json
import logging
from collections import deque
from pathlib import Path

logger = logging.getLogger(__name__)

# Minimum number of records before we start generating policy hints
MIN_RECORDS_FOR_HINT = 5


class FeedbackMemory:
    """
    Reinforcement Learning component for SHAPE.

    Mechanism
    ---------
    1. **Feedback**: After each response the user rates it 1–5.
    2. **Reward signal**: Average score over a rolling window of 20 turns.
    3. **Policy improvement**: If average score drops below 3.0, a correction
       hint is prepended to the agent's next prompt, nudging it to be more
       careful/detailed. If average is ≥ 4.0, a positive hint acknowledges
       the working strategy and encourages consistency.
    4. **Persistence**: Records are appended to a JSONL file so learning
       survives session restarts (important on Pi — no cloud state).

    This is an approximation of a bandit/policy-gradient loop without full
    RL infrastructure, appropriate for a course-level demonstration.
    """

    WINDOW = 20  # rolling average window size

    def __init__(self, history_path: Path) -> None:
        self.history_path = history_path
        history_path.parent.mkdir(parents=True, exist_ok=True)
        self._buffer: deque[dict] = deque(maxlen=self.WINDOW)
        self._load_recent()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_recent(self) -> None:
        """Load the last WINDOW records from disk on startup."""
        if not self.history_path.exists():
            return
        try:
            lines = self.history_path.read_text(encoding="utf-8").splitlines()
            for line in lines[-self.WINDOW:]:
                self._buffer.append(json.loads(line))
            logger.info("FeedbackMemory: loaded %d recent records.", len(self._buffer))
        except Exception as exc:  # noqa: BLE001
            logger.warning("FeedbackMemory: could not load history: %s", exc)

    def record(self, entry: dict) -> None:
        """Append one feedback entry and persist it."""
        self._buffer.append(entry)
        try:
            with self.history_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except Exception as exc:  # noqa: BLE001
            logger.warning("FeedbackMemory: could not write record: %s", exc)

    # ------------------------------------------------------------------
    # Policy hint (injected into next prompt)
    # ------------------------------------------------------------------

    def get_policy_hint(self) -> str:
        """
        Return a one-line policy hint based on recent feedback scores.

        Returns an empty string if there is not enough data yet.
        """
        if len(self._buffer) < MIN_RECORDS_FOR_HINT:
            return ""

        scores = [r["score"] for r in self._buffer if "score" in r]
        if not scores:
            return ""

        avg = sum(scores) / len(scores)

        if avg < 2.5:
            return (
                "[SHAPE Policy Hint] Recent responses scored poorly. "
                "Be more thorough: think step-by-step, test your code before "
                "returning it, and explain each decision clearly."
            )
        elif avg < 3.5:
            return (
                "[SHAPE Policy Hint] Recent responses were average. "
                "Double-check edge cases and always lint before executing."
            )
        else:
            # High average — reinforce what's working
            return (
                "[SHAPE Policy Hint] Recent responses scored well. "
                "Keep following the same careful, step-by-step approach."
            )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        """Return statistics about collected feedback (for the CLI status command)."""
        scores = [r["score"] for r in self._buffer if "score" in r]
        if not scores:
            return {"records": 0, "avg_score": None, "policy": "insufficient data"}
        avg = round(sum(scores) / len(scores), 2)
        return {
            "records": len(scores),
            "avg_score": avg,
            "policy": self.get_policy_hint() or "no hint (insufficient data)",
        }
