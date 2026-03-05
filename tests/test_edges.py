"""Tests for graph edge routing logic (src/graph/edges.py)"""

from src.graph.edges import should_abort, has_results


def test_should_abort_returns_abort_on_error():
    state = {"query": "test", "error": "something went wrong"}
    assert should_abort(state) == "abort"


def test_should_abort_returns_continue_without_error():
    state = {"query": "test", "error": None}
    assert should_abort(state) == "continue"


def test_should_abort_returns_continue_when_no_error_key():
    state = {"query": "test"}
    assert should_abort(state) == "continue"


def test_has_results_returns_ok_with_results():
    state = {"search_results": [{"url": "https://a.com"}]}
    assert has_results(state) == "ok"


def test_has_results_returns_empty_with_no_results():
    state = {"search_results": []}
    assert has_results(state) == "empty"


def test_has_results_returns_empty_when_missing():
    state = {}
    assert has_results(state) == "empty"
