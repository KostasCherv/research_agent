from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.sidecar.app import app


client = TestClient(app)


def test_sidecar_ingest_query_and_delete_flow(tmp_path: Path):
    source_file = tmp_path / "sample.txt"
    source_file.write_text("LangGraph enables agent workflows with graphs.", encoding="utf-8")

    with patch("src.sidecar.app.settings.rag_sidecar_persist_directory", str(tmp_path / "sidecar")):
        ingest = client.post(
            "/ingest",
            json={
                "resource_id": "res-1",
                "file_locator": str(source_file),
                "owner_scope": "user-1",
                "workspace_id": "ws-1",
                "job_id": "job-1",
            },
        )
        assert ingest.status_code == 200

        status = client.get("/ingest/job-1")
        assert status.status_code == 200
        assert status.json()["status"] == "succeeded"

        query = client.post(
            "/query",
            json={
                "agent_id": "agent-1",
                "resource_ids": ["res-1"],
                "query": "What is LangGraph?",
                "owner_scope": "user-1",
                "workspace_id": "ws-1",
            },
        )
        assert query.status_code == 200
        payload = query.json()
        assert "context" in payload
        assert isinstance(payload["chunks"], list)

        delete = client.delete("/resource/res-1")
        assert delete.status_code == 200
        assert delete.json()["deleted"] is True
