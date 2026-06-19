"""Unit tests for session store — file-based, deterministic."""
import time
import pytest
from pathlib import Path
from memory.session import SessionStore


@pytest.fixture
def store(tmp_path):
    return SessionStore(storage_dir=str(tmp_path / "sessions"))


class TestSessionStore:
    def test_empty_history(self, store):
        assert store.get_history("no_such_session") == []

    def test_add_and_retrieve_turn(self, store):
        store.add_turn("s1", "query1", "answer1", ["orders"], "SELECT 1")
        history = store.get_history("s1")
        assert len(history) == 1
        assert history[0]["query"] == "query1"
        assert history[0]["answer"] == "answer1"
        assert history[0]["matched_tables"] == ["orders"]
        assert history[0]["sql"] == "SELECT 1"

    def test_format_for_prompt(self, store):
        store.add_turn("s2", "how many orders", "99441 orders", ["orders"], "SELECT count(*) FROM orders")
        prompt = store.format_for_prompt("s2")
        assert "how many orders" in prompt
        assert "orders" in prompt  # table name in IMPORTANT directive

    def test_format_last_tables_included(self, store):
        store.add_turn("s3", "top sellers", "result", ["sellers", "order_items"], "SELECT ...")
        prompt = store.format_for_prompt("s3")
        assert "sellers" in prompt
        assert "order_items" in prompt

    def test_trim_old_turns(self, store):
        for i in range(15):
            store.add_turn("s4", f"q{i}", f"a{i}", ["t"], "SQL")
        history = store.get_history("s4")
        assert len(history) == 10  # max_turns default is 10

    def test_clear_session(self, store):
        store.add_turn("s5", "q", "a", [], "")
        store.clear("s5")
        assert store.get_history("s5") == []
