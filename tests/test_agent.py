"""Tests for shape.agent — safety, memory trimming, 8-step cap."""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from shape.safety  import InputGuard
from shape.memory  import make_history, trimmed_messages
from shape.parser  import parse_llm_output
from shape.rewards import FeedbackMemory, MIN_RECORDS_FOR_HINT
from pathlib import Path
import tempfile


class TestInputGuard:
    def setup_method(self):
        self.g = InputGuard({})

    def test_allows_normal_query(self):
        blocked, _ = self.g.check("Write a sort function in Python")
        assert not blocked

    def test_blocks_rm_rf(self):
        blocked, reason = self.g.check("rm -rf /")
        assert blocked
        assert reason

    def test_blocks_os_system(self):
        blocked, _ = self.g.check("os.system('ls')")
        assert blocked

    def test_blocks_malware(self):
        blocked, _ = self.g.check("generate a virus worm")
        assert blocked

    def test_blocks_out_of_scope(self):
        blocked, _ = self.g.check("Give me legal advice on my lawsuit")
        assert blocked

    def test_length_limit(self):
        blocked, _ = self.g.check("A" * 8001)
        assert blocked


class TestMemoryTrimming:
    def test_window_trimming(self):
        h = make_history()
        for i in range(10):
            h.add_user_message(f"q{i}")
            h.add_ai_message(f"a{i}")
        # window=3 → last 6 messages
        msgs = trimmed_messages(h, window=3)
        assert len(msgs) == 6

    def test_empty_history(self):
        h = make_history()
        msgs = trimmed_messages(h, window=6)
        assert msgs == []


class TestFeedbackMemory:
    def setup_method(self):
        self.tmp = Path(tempfile.mktemp(suffix=".jsonl"))
        self.fm = FeedbackMemory(self.tmp)

    def teardown_method(self):
        if self.tmp.exists():
            self.tmp.unlink()

    def test_no_hint_before_min_records(self):
        for i in range(MIN_RECORDS_FOR_HINT - 1):
            self.fm.record({"score": 5})
        assert self.fm.get_policy_hint() == ""

    def test_correction_hint_low_scores(self):
        for _ in range(MIN_RECORDS_FOR_HINT):
            self.fm.record({"score": 1})
        hint = self.fm.get_policy_hint()
        assert "thorough" in hint.lower() or "poorly" in hint.lower()

    def test_positive_hint_high_scores(self):
        for _ in range(MIN_RECORDS_FOR_HINT):
            self.fm.record({"score": 5})
        hint = self.fm.get_policy_hint()
        assert "well" in hint.lower() or "keep" in hint.lower()

    def test_persistence(self):
        self.fm.record({"score": 4, "input": "x", "output": "y"})
        fm2 = FeedbackMemory(self.tmp)
        assert len(fm2._buffer) == 1
