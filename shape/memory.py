"""
shape.memory — Conversation memory for SHAPE.

Thin wrapper around LangChain InMemoryChatMessageHistory that exposes
the sliding-window trimming logic as a reusable function.

Notebook 02 demonstrates this module; test_agent.py validates window trimming.

Group 3 — ITAI2376-14562
"""
from __future__ import annotations

from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import BaseMessage


def make_history() -> InMemoryChatMessageHistory:
    """Return a fresh chat history store."""
    return InMemoryChatMessageHistory()


def trimmed_messages(
    history: InMemoryChatMessageHistory,
    window: int,
) -> list[BaseMessage]:
    """
    Return the last `window * 2` messages from history.

    Each conversational turn consists of one HumanMessage and one AIMessage,
    so window=6 means the last 6 complete turns (12 messages).
    """
    return list(history.messages)[-(window * 2):]
