"""
SHAPE Tools package — exports get_tools() for the agent.

Group 3 — ITAI2376-14562
Members: Cherluk Sumdin, Olubukola Kukoyi, Taki Eddine Boubekri, Michael Rivas
"""

from typing import Any

from langchain_core.tools import Tool

from .code_executor import CodeExecutorTool
from .doc_search import DocSearchTool
from .file_manager import FileManagerTool
from .linter import LinterTool


def get_tools(config: dict[str, Any]) -> list[Tool]:
    """Return the list of LangChain tools available to the SHAPE agent."""
    return [
        CodeExecutorTool(config).as_tool(),
        LinterTool(config).as_tool(),
        FileManagerTool(config).as_tool(),
        DocSearchTool(config).as_tool(),
    ]
