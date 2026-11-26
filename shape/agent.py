"""
SHAPE — Self-Healing Autonomous Programming Engine
Core agent module: ReAct pattern over Ollama (CodeLlama 7B, offline)

Uses a prompt-based ReAct loop compatible with any text/chat model (no native
tool-calling required). Works with LangChain 1.x / LangGraph 0.4+.

Group 3 — ITAI2376-14562
Members: Cherluk Sumdin, Olubukola Kukoyi, Taki Eddine Boubekri, Michael Rivas
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.chat_history import InMemoryChatMessageHistory

from shape.feedback import FeedbackMemory
from shape.safety import InputGuard
from shape.tools import get_tools

logger = logging.getLogger(__name__)

REACT_SYSTEM = """You are SHAPE, a Self-Healing Autonomous Programming Engine running offline.
You help users write, debug, and improve code using the following tools:

{tool_descriptions}

Use this EXACT format for every response:

Thought: <your reasoning about what to do next>
Action: <tool name, must be one of: {tool_names}>
Action Input: <the input to the tool, as plain text>

When you have a final answer (no more tool calls needed), respond EXACTLY like:

Thought: I now have the final answer.
Final Answer: <your complete answer to the user>

Rules:
- Always think before acting.
- If a tool returns an error, reflect and try a different approach.
- Never fabricate tool outputs.
- When writing code, lint it first, then execute it.
"""


def build_agent(config: dict[str, Any]) -> "SHAPEAgent":
    return SHAPEAgent(config)


class SHAPEAgent:
    """
    SHAPE agent using a prompt-based ReAct loop.
    Works with any Ollama model — no native tool-calling API required.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self._setup_llm()
        self.tools_list = get_tools(config)
        self.tools_by_name = {t.name: t for t in self.tools_list}
        self._chat_history = InMemoryChatMessageHistory()
        self.guard = InputGuard(config.get("safety", {}))
        self.feedback = FeedbackMemory(
            history_path=Path(config.get("feedback_path", "data/feedback.jsonl"))
        )
        logger.info("SHAPE agent initialised (model=%s)", config.get("model", "codellama"))

    def _setup_llm(self) -> None:
        # IMPORTANT: We use a prompt-based ReAct loop — the LLM must receive
        # plain text only. Do NOT pass tools= to ChatOllama; that triggers
        # Ollama's native tool-calling API which CodeLlama does not support
        # (HTTP 400 "does not support tools"). Tools are dispatched manually
        # in run() after parsing the LLM's text output.
        llm_kwargs = dict(
            model=self.config.get("model", "codellama"),
            base_url=self.config.get("ollama_url", "http://localhost:11434"),
            temperature=self.config.get("temperature", 0.2),
            num_ctx=self.config.get("context_window", 4096),
        )
        try:
            from langchain_ollama import ChatOllama
            self.llm = ChatOllama(**llm_kwargs)
        except ImportError:
            from langchain_community.chat_models import ChatOllama
            self.llm = ChatOllama(**llm_kwargs)

    def _build_system_prompt(self) -> str:
        descriptions = "\n".join(
            f"- {t.name}: {t.description}" for t in self.tools_list
        )
        names = ", ".join(t.name for t in self.tools_list)
        return REACT_SYSTEM.format(tool_descriptions=descriptions, tool_names=names)

    def _parse_llm_output(self, text: str) -> dict:
        """Parse ReAct output: returns {type: "action"|"final", ...}"""
        # Check for Final Answer first
        fa_match = re.search(r"Final Answer\s*:\s*(.+)", text, re.DOTALL | re.IGNORECASE)
        if fa_match:
            return {"type": "final", "answer": fa_match.group(1).strip()}

        # Check for Action
        action_match = re.search(r"Action\s*:\s*(.+)", text)
        input_match = re.search(r"Action Input\s*:\s*(.+)", text, re.DOTALL)
        if action_match:
            return {
                "type": "action",
                "tool": action_match.group(1).strip(),
                "input": input_match.group(1).strip() if input_match else "",
            }

        # Treat plain response as final answer
        return {"type": "final", "answer": text.strip()}

    def run(self, user_input: str) -> str:
        # Safety check
        blocked, reason = self.guard.check(user_input)
        if blocked:
            return f"[SHAPE] I cannot help with that. Reason: {reason}"

        hint = self.feedback.get_policy_hint()
        system_text = self._build_system_prompt()
        if hint:
            system_text += f"\n\n{hint}"

        # Build conversation context
        window = self.config.get("memory_window", 6)
        history_msgs = self._chat_history.messages[-(window * 2):]

        # ReAct loop
        max_iter = self.config.get("max_iterations", 8)
        messages = [SystemMessage(content=system_text)]
        messages.extend(history_msgs)
        messages.append(HumanMessage(content=user_input))

        answer = "[SHAPE] Could not produce a response."
        try:
            for i in range(max_iter):
                # invoke() with a plain list — no config= or kwargs that
                # could carry tool schemas to Ollama.
                response = self.llm.invoke(messages)
                text = response.content if hasattr(response, "content") else str(response)

                if self.config.get("verbose", False):
                    print(f"\n[Step {i+1}]\n{text}\n")

                parsed = self._parse_llm_output(text)

                if parsed["type"] == "final":
                    answer = parsed["answer"]
                    break

                # Execute tool
                tool_name = parsed["tool"]
                tool_input = parsed["input"]
                tool = self.tools_by_name.get(tool_name)
                if tool is None:
                    observation = f"Error: unknown tool '{tool_name}'. Available: {list(self.tools_by_name)}"
                else:
                    try:
                        observation = tool.invoke(tool_input)
                    except Exception as e:
                        observation = f"Tool error: {e}"

                # Append assistant turn + observation to messages
                messages.append(AIMessage(content=text))
                messages.append(HumanMessage(content=f"Observation: {observation}"))

        except Exception as exc:
            logger.error("Agent execution error: %s", exc)
            answer = (
                f"[SHAPE] An internal error occurred: {exc}\n"
                "Please rephrase your request or simplify the task."
            )
            return answer

        self._chat_history.add_user_message(user_input)
        self._chat_history.add_ai_message(answer)
        return answer

    def collect_feedback(self, user_input: str, answer: str, score: int) -> None:
        if not 1 <= score <= 5:
            raise ValueError("Score must be between 1 and 5.")
        self.feedback.record({"input": user_input, "output": answer, "score": score})
        logger.info("Feedback recorded: score=%d", score)

    def reset_session(self) -> None:
        self._chat_history.clear()
        logger.info("Session memory cleared.")
