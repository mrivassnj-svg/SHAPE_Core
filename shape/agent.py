"""
shape.agent — SHAPE ReAct agent (canonical implementation).

All notebooks import build_agent() from here.
No notebook re-implements the loop.

Depends on:
    shape.prompts  — REACT_SYSTEM template
    shape.parser   — parse_llm_output()
    shape.memory   — make_history(), trimmed_messages()
    shape.rewards  — FeedbackMemory
    shape.safety   — InputGuard
    shape.tools    — get_tools()

Group 3 — ITAI2376-14562
Members: Cherluk Sumdin, Olubukola Kukoyi, Taki Eddine Boubekri, Michael Rivas
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from shape.memory  import make_history, trimmed_messages
from shape.parser  import parse_llm_output
from shape.prompts import REACT_SYSTEM
from shape.rewards import FeedbackMemory
from shape.safety  import InputGuard
from shape.tools   import get_tools

logger = logging.getLogger(__name__)


def build_agent(config: dict[str, Any]) -> "SHAPEAgent":
    """Factory — the only constructor notebooks should call."""
    return SHAPEAgent(config)


class SHAPEAgent:
    """
    SHAPE ReAct agent.

    One canonical implementation shared by all four notebooks and all tests.

    Architecture
    ------------
    user_input
      → InputGuard.check()          (shape.safety)
      → build SystemMessage          (shape.prompts + FeedbackMemory hint)
      → for step in range(max_iter):
            llm.invoke(messages)     (ChatOllama, plain text — no tool schemas)
            parse_llm_output(text)   (shape.parser)
            → "action"  → tool.invoke(input)   → Observation
            → "final"   → break
      → persist to InMemoryChatMessageHistory  (shape.memory)
      → return answer
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config       = config
        self.llm          = _build_llm(config)
        self.tools_list   = get_tools(config)
        self.tools_by_name = {t.name: t for t in self.tools_list}
        self._history     = make_history()
        self.guard        = InputGuard(config.get("safety", {}))
        self.feedback     = FeedbackMemory(
            Path(config.get("feedback_path", "data/feedback.jsonl"))
        )
        logger.info("SHAPEAgent ready (model=%s)", config.get("model", "codellama"))

    # ── public API ────────────────────────────────────────────────────

    def run(self, user_input: str) -> str:
        """Process one user request through the full ReAct loop."""
        blocked, reason = self.guard.check(user_input)
        if blocked:
            return f"[SHAPE] I cannot help with that. Reason: {reason}"

        system_text = _build_system_prompt(self.tools_list, self.feedback)
        window      = self.config.get("memory_window", 6)
        max_iter    = self.config.get("max_iterations", 8)
        verbose     = self.config.get("verbose", False)

        messages = (
            [SystemMessage(content=system_text)]
            + trimmed_messages(self._history, window)
            + [HumanMessage(content=user_input)]
        )

        answer = "[SHAPE] Could not produce a response."
        try:
            for i in range(max_iter):
                response = self.llm.invoke(messages)
                text     = response.content if hasattr(response, "content") else str(response)
                if verbose:
                    print(f"\n[Step {i+1}]\n{text}\n")

                parsed = parse_llm_output(text)

                if parsed["type"] == "final":
                    answer = parsed["answer"]
                    break

                tool      = self.tools_by_name.get(parsed["tool"])
                observation = (
                    tool.invoke(parsed["input"])
                    if tool is not None
                    else f"Error: unknown tool '{parsed['tool']}'. "
                         f"Available: {list(self.tools_by_name)}"
                )
                messages += [
                    AIMessage(content=text),
                    HumanMessage(content=f"Observation: {observation}"),
                ]
        except Exception as exc:
            logger.error("Agent error: %s", exc)
            return f"[SHAPE] Internal error: {exc}"

        self._history.add_user_message(user_input)
        self._history.add_ai_message(answer)
        return answer

    def collect_feedback(self, user_input: str, answer: str, score: int) -> None:
        """Record a 1-5 user rating for the RL reward loop."""
        if not 1 <= score <= 5:
            raise ValueError("Score must be 1-5.")
        self.feedback.record({"input": user_input, "output": answer, "score": score})

    def reset_session(self) -> None:
        """Clear conversation memory for a new session."""
        self._history.clear()


# ── private helpers ───────────────────────────────────────────────────────────

def _build_llm(config: dict[str, Any]):
    """
    Construct a ChatOllama instance.

    IMPORTANT: Do NOT pass tools= to ChatOllama. CodeLlama does not support
    Ollama's native tool-calling API (HTTP 400). Tool dispatch is handled
    entirely in the ReAct loop above using parse_llm_output().
    """
    kwargs = dict(
        model    = config.get("model",       "codellama"),
        base_url = config.get("ollama_url",  "http://localhost:11434"),
        temperature = config.get("temperature",  0.2),
        num_ctx     = config.get("context_window", 4096),
    )
    try:
        from langchain_ollama import ChatOllama
        return ChatOllama(**kwargs)
    except ImportError:
        from langchain_community.chat_models import ChatOllama
        return ChatOllama(**kwargs)


def _build_system_prompt(tools_list, feedback: FeedbackMemory) -> str:
    descriptions = "\n".join(f"- {t.name}: {t.description}" for t in tools_list)
    names        = ", ".join(t.name for t in tools_list)
    text         = REACT_SYSTEM.format(tool_descriptions=descriptions, tool_names=names)
    hint         = feedback.get_policy_hint()
    return text + f"\n\n{hint}" if hint else text
