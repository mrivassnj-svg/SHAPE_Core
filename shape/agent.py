"""
SHAPE — Self-Healing Autonomous Programming Engine
Core agent module: ReAct pattern over Ollama (CodeLlama 7B, offline)

Uses LangGraph's create_react_agent (compatible with LangChain 1.x / LangGraph 0.4+).

Group 3 — ITAI2376-14562
Members: Cherluk Sumdin, Olubukola Kukoyi, Taki Eddine Boubekri, Michael Rivas
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.chat_history import InMemoryChatMessageHistory
from langgraph.prebuilt import create_react_agent

from shape.feedback import FeedbackMemory
from shape.safety import InputGuard
from shape.tools import get_tools

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are SHAPE, a Self-Healing Autonomous Programming Engine running on a
Raspberry Pi. You help users write, debug, and improve code — entirely offline.

Always think step-by-step before choosing a tool. If a tool fails, reflect on
the error and try an alternative approach. Never fabricate tool outputs.
When generating code, always lint it first, then execute it to verify it works.
"""


def build_agent(config: dict[str, Any]) -> "SHAPEAgent":
    """Factory: build and return a fully wired SHAPEAgent from a config dict."""
    return SHAPEAgent(config)


class SHAPEAgent:
    """
    Main SHAPE agent.

    Architecture
    ------------
    Input  → InputGuard (safety) → LangGraph ReAct agent (Ollama / CodeLlama)
           → Tools (executor, linter, file manager, doc search)
           → Output → FeedbackMemory (RL reward loop)

    Uses InMemoryChatMessageHistory for sliding-window conversation memory.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self._setup_llm()
        self._setup_tools()
        self._setup_executor()
        self._chat_history = InMemoryChatMessageHistory()
        self.guard = InputGuard(config.get("safety", {}))
        self.feedback = FeedbackMemory(
            history_path=Path(config.get("feedback_path", "data/feedback.jsonl"))
        )
        logger.info("SHAPE agent initialised (model=%s)", config.get("model", "codellama"))

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def _setup_llm(self) -> None:
        """Connect to local Ollama instance."""
        try:
            from langchain_ollama import OllamaLLM
            self.llm = OllamaLLM(
                model=self.config.get("model", "codellama"),
                base_url=self.config.get("ollama_url", "http://localhost:11434"),
                temperature=self.config.get("temperature", 0.2),
                num_ctx=self.config.get("context_window", 4096),
            )
        except ImportError:
            # Fallback to langchain-community Ollama wrapper
            from langchain_community.llms import Ollama
            self.llm = Ollama(
                model=self.config.get("model", "codellama"),
                base_url=self.config.get("ollama_url", "http://localhost:11434"),
                temperature=self.config.get("temperature", 0.2),
                num_ctx=self.config.get("context_window", 4096),
            )

    def _setup_tools(self) -> None:
        self.tools = get_tools(self.config)

    def _setup_executor(self) -> None:
        self.executor = create_react_agent(
            self.llm,
            self.tools,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, user_input: str) -> str:
        """
        Process a user coding request end-to-end.

        1. Safety screen the input.
        2. Retrieve past feedback to prepend policy hints.
        3. Run the ReAct executor with conversation history.
        4. Return the final answer.
        """
        # Step 1 — safety
        blocked, reason = self.guard.check(user_input)
        if blocked:
            logger.warning("Input blocked: %s", reason)
            return f"[SHAPE] I cannot help with that request. Reason: {reason}"

        # Step 2 — inject RL policy hint
        hint = self.feedback.get_policy_hint()

        # Build message list: system prompt + history + current input
        messages: list = []

        system_text = SYSTEM_PROMPT
        if hint:
            system_text += f"\n\n{hint}"
        messages.append(SystemMessage(content=system_text))

        # Append rolling conversation history (last memory_window turns)
        window = self.config.get("memory_window", 6)
        history_msgs = self._chat_history.messages[-(window * 2):]
        messages.extend(history_msgs)

        messages.append(HumanMessage(content=user_input))

        # Step 3 — run agent
        try:
            result = self.executor.invoke({"messages": messages})
            # LangGraph returns {"messages": [...]} — last message is the answer
            answer_msg = result["messages"][-1]
            answer = answer_msg.content if hasattr(answer_msg, "content") else str(answer_msg)
        except Exception as exc:  # noqa: BLE001
            logger.error("Agent execution error: %s", exc)
            answer = (
                f"[SHAPE] An internal error occurred: {exc}\n"
                "Please rephrase your request or simplify the task."
            )
            return answer

        # Persist this exchange to history
        self._chat_history.add_user_message(user_input)
        self._chat_history.add_ai_message(answer)

        return answer

    def collect_feedback(self, user_input: str, answer: str, score: int) -> None:
        """
        Record user feedback (1–5 score) for the RL reward loop.
        """
        if not 1 <= score <= 5:
            raise ValueError("Score must be between 1 and 5.")
        self.feedback.record({"input": user_input, "output": answer, "score": score})
        logger.info("Feedback recorded: score=%d", score)

    def reset_session(self) -> None:
        """Clear conversation memory for a fresh session."""
        self._chat_history.clear()
        logger.info("Session memory cleared.")
