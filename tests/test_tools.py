"""Tests for shape.tools — all error paths."""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from shape.tools.linter        import LinterTool
from shape.tools.code_executor import CodeExecutorTool
from shape.tools.file_manager  import FileManagerTool
import json, tempfile, pathlib


class TestLinter:
    def setup_method(self):
        self.linter = LinterTool({})

    def test_clean_code(self):
        out = self.linter._run("def f(x):\n    return x + 1\n")
        assert "No issues" in out or out.strip() == ""

    def test_empty_input(self):
        out = self.linter._run("")
        assert "Empty" in out or "nothing" in out.lower()

    def test_undefined_name(self):
        out = self.linter._run("print(undefined_var)\n")
        assert "undefined" in out.lower() or "undefined_var" in out


class TestCodeExecutor:
    def setup_method(self):
        self.ex = CodeExecutorTool({"executor_timeout": 5, "executor_max_output": 4096})

    def test_simple_output(self):
        out = self.ex._run("print(2 + 2)")
        assert "4" in out

    def test_empty_input(self):
        out = self.ex._run("")
        assert "Empty" in out or "nothing" in out.lower()

    def test_timeout(self):
        fast = CodeExecutorTool({"executor_timeout": 1, "executor_max_output": 512})
        out = fast._run("import time; time.sleep(999)")
        assert "timed out" in out.lower()

    def test_runtime_error_captured(self):
        out = self.ex._run("raise ValueError('test error')")
        assert "ValueError" in out or "test error" in out


class TestFileManager:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.fm = FileManagerTool({"workspace_dir": self.tmp})

    def test_write_and_read(self):
        self.fm._run(json.dumps({"action": "write", "path": "a.txt", "content": "hello"}))
        out = self.fm._run(json.dumps({"action": "read", "path": "a.txt"}))
        assert out == "hello"

    def test_path_traversal_blocked(self):
        out = self.fm._run(json.dumps({"action": "read", "path": "../../etc/passwd"}))
        assert "traversal" in out.lower() or "denied" in out.lower()

    def test_missing_file(self):
        out = self.fm._run(json.dumps({"action": "read", "path": "nonexistent.txt"}))
        assert "not found" in out.lower()

    def test_unknown_action(self):
        out = self.fm._run(json.dumps({"action": "delete", "path": "a.txt"}))
        assert "Unknown" in out or "unknown" in out
