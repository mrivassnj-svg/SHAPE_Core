"""Tests for shape.parser.parse_llm_output() — all three branches."""
import pytest
from shape.parser import parse_llm_output


class TestFinalAnswerBranch:
    def test_basic_final_answer(self):
        r = parse_llm_output("Thought: done.\nFinal Answer: def f(): pass")
        assert r["type"] == "final"
        assert "def f(): pass" in r["answer"]

    def test_case_insensitive(self):
        r = parse_llm_output("FINAL ANSWER: hello")
        assert r["type"] == "final"
        assert r["answer"] == "hello"

    def test_multiline_final_answer(self):
        r = parse_llm_output("Final Answer: line1\nline2\nline3")
        assert r["type"] == "final"
        assert "line1" in r["answer"]
        assert "line3" in r["answer"]


class TestActionBranch:
    def test_basic_action(self):
        r = parse_llm_output("Thought: lint it.\nAction: linter\nAction Input: def f(): pass")
        assert r["type"] == "action"
        assert r["tool"] == "linter"
        assert "def f()" in r["input"]

    def test_all_four_tools(self):
        for tool in ("linter", "code_executor", "file_manager", "doc_search"):
            r = parse_llm_output(f"Action: {tool}\nAction Input: test")
            assert r["tool"] == tool

    def test_missing_input_defaults_empty(self):
        r = parse_llm_output("Action: linter")
        assert r["type"] == "action"
        assert r["input"] == ""


class TestFallbackBranch:
    def test_plain_text_becomes_final(self):
        r = parse_llm_output("Here is a simple solution: print('hello')")
        assert r["type"] == "final"

    def test_empty_string(self):
        r = parse_llm_output("")
        assert r["type"] == "final"
        assert r["answer"] == ""


class TestPriority:
    def test_final_answer_beats_action(self):
        """Final Answer should win even if Action appears first."""
        text = "Action: linter\nAction Input: x\nFinal Answer: done"
        r = parse_llm_output(text)
        assert r["type"] == "final"
