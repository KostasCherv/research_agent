"""Tests for observability helpers and redaction behavior."""

from src.observability.context import build_trace_metadata, build_trace_tags
from src.observability.langsmith import end_workflow_run, start_step_span, start_workflow_run
from src.observability.redaction import REDACTED, redact_payload


def test_redaction_default_censors_sensitive_keys():
    payload = {
        "query": "secret query",
        "count": 3,
        "nested": {"prompt": "do not leak", "ok": True},
    }
    out = redact_payload(payload, mode="redacted_default")
    assert out["query"] == REDACTED
    assert out["count"] == 3
    assert out["nested"]["prompt"] == REDACTED
    assert out["nested"]["ok"] is True


def test_redaction_metadata_only_shapes_data():
    payload = {"query": "abc", "items": [1, 2, 3]}
    out = redact_payload(payload, mode="metadata_only")
    assert out == {"type": "dict", "size": 2}


def test_workflow_run_context_populates_metadata_when_disabled(monkeypatch):
    from src.observability import langsmith as ls
    monkeypatch.setattr(ls.settings, "langsmith_tracing", False)

    with start_workflow_run(
        entrypoint="test",
        query="hello",
        use_vector_store=False,
    ) as ctx:
        assert ctx.workflow_id
        assert ctx.entrypoint == "test"
        assert ctx.tracing_enabled is False

        metadata = build_trace_metadata({"k": "v"})
        tags = build_trace_tags(["extra"])
        assert metadata["workflow_id"] == ctx.workflow_id
        assert metadata["entrypoint"] == "test"
        assert "entrypoint:test" in tags
        assert "extra" in tags

        # Should no-op when tracing is disabled.
        with start_step_span(name="dummy-step", run_type="tool"):
            pass

    # Should no-op when run is disabled.
    end_workflow_run(ctx, status="success", outputs={"ok": True})
