from io import BytesIO
from unittest.mock import AsyncMock, patch

from starlette.datastructures import UploadFile

from src.rag import (
    RagValidationError,
    _run_ingestion_job,
    create_resource_and_ingest,
    process_queued_ingestion_jobs,
    run_ingestion_job_now,
)


async def test_create_resource_rejects_unsupported_extension():
    file = UploadFile(filename="notes.exe", file=BytesIO(b"abc"), headers={"content-type": "text/plain"})
    with patch("src.rag._get_store", return_value=AsyncMock()):
        try:
            await create_resource_and_ingest(file, "user-1")
            assert False, "Expected RagValidationError"
        except RagValidationError as exc:
            assert exc.code == "unsupported_type"


async def test_run_ingestion_job_marks_ready_on_success():
    mock_store = AsyncMock()
    mock_store.get_rag_ingestion_job.return_value = {
        "job_id": "job-1",
        "resource_id": "res-1",
        "owner_id": "user-1",
        "workspace_id": "user-1",
        "status": "queued",
        "stage": "queued",
        "retries": 0,
        "max_retries": 1,
        "error_details": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    mock_store.get_rag_resource.return_value = {
        "resource_id": "res-1",
        "owner_id": "user-1",
        "workspace_id": "user-1",
        "filename": "doc.txt",
        "mime_type": "text/plain",
        "byte_size": 12,
        "storage_uri": "/tmp/doc.txt",
        "state": "uploaded",
        "error_details": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }

    mock_storage = AsyncMock()
    mock_storage.create_signed_download_url = AsyncMock(return_value="https://signed-url")

    with (
        patch("src.rag._get_store", return_value=mock_store),
        patch("src.rag._get_storage", return_value=mock_storage),
        patch("src.rag.ingest_resource_from_locator", new=AsyncMock(return_value=3)),
    ):
        await _run_ingestion_job("job-1")

    assert mock_store.update_rag_resource.await_count >= 1
    assert any(
        call.args[1].get("state") == "ready"
        for call in mock_store.update_rag_resource.await_args_list
    )


async def test_run_ingestion_job_marks_failed_after_retries():
    mock_store = AsyncMock()
    mock_store.get_rag_ingestion_job.return_value = {
        "job_id": "job-1",
        "resource_id": "res-1",
        "owner_id": "user-1",
        "workspace_id": "user-1",
        "status": "queued",
        "stage": "queued",
        "retries": 0,
        "max_retries": 1,
        "error_details": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    mock_store.get_rag_resource.return_value = {
        "resource_id": "res-1",
        "owner_id": "user-1",
        "workspace_id": "user-1",
        "filename": "doc.txt",
        "mime_type": "text/plain",
        "byte_size": 12,
        "storage_uri": "/tmp/doc.txt",
        "state": "uploaded",
        "error_details": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }

    mock_storage = AsyncMock()
    mock_storage.create_signed_download_url = AsyncMock(return_value="https://signed-url")

    with (
        patch("src.rag._get_store", return_value=mock_store),
        patch("src.rag._get_storage", return_value=mock_storage),
        patch("src.rag.ingest_resource_from_locator", new=AsyncMock(side_effect=RuntimeError("ingest failed"))),
    ):
        await _run_ingestion_job("job-1")

    assert any(
        call.args[1].get("state") == "failed"
        for call in mock_store.update_rag_resource.await_args_list
    )


async def test_process_queued_ingestion_jobs_processes_all_selected_jobs():
    mock_store = AsyncMock()
    mock_store.list_rag_ingestion_jobs_for_processing.return_value = [
        {"job_id": "job-1"},
        {"job_id": "job-2"},
    ]

    with (
        patch("src.rag._get_store", return_value=mock_store),
        patch("src.rag._run_ingestion_job", new=AsyncMock(return_value=None)) as mock_run,
    ):
        processed = await process_queued_ingestion_jobs(limit=10)

    assert processed == 2
    assert mock_run.await_count == 2


async def test_create_resource_writes_outbox_event():
    file = UploadFile(
        filename="notes.txt",
        file=BytesIO(b"hello world"),
        headers={"content-type": "text/plain"},
    )
    mock_store = AsyncMock()
    mock_store.count_rag_resources_in_workspace.return_value = 0
    mock_storage = AsyncMock()
    mock_storage.upload_bytes = AsyncMock(return_value="supabase://rag-resources/user-1/path")

    with (
        patch("src.rag._get_store", return_value=mock_store),
        patch("src.rag._get_storage", return_value=mock_storage),
    ):
        resource, job = await create_resource_and_ingest(file, "user-1")

    assert mock_store.create_resource_job_and_outbox.await_count == 1
    call_kwargs = mock_store.create_resource_job_and_outbox.await_args.kwargs
    outbox = call_kwargs["outbox_payload"]
    assert outbox["event_name"] == "rag/ingestion.requested"
    assert outbox["payload"]["job_id"] == job.job_id
    assert outbox["payload"]["resource_id"] == resource.resource_id
    assert outbox["payload"]["owner_id"] == "user-1"
    assert "workspace_id" in outbox["payload"]
    # resource and job must NOT be written separately — the RPC handles everything
    mock_store.create_rag_resource.assert_not_awaited()
    mock_store.create_rag_ingestion_job.assert_not_awaited()


async def test_claim_succeeds_for_queued_job_and_fails_on_second_attempt():
    mock_store = AsyncMock()
    mock_store.claim_rag_ingestion_job.side_effect = [True, False]

    with patch("src.rag._get_store", return_value=mock_store):
        with patch("src.rag._run_ingestion_job", new=AsyncMock()):
            first = await run_ingestion_job_now("job-1")
            second = await run_ingestion_job_now("job-1")

    assert first is True
    assert second is False


async def test_run_ingestion_job_now_skips_when_already_terminal():
    mock_store = AsyncMock()
    mock_store.claim_rag_ingestion_job.return_value = False

    with patch("src.rag._get_store", return_value=mock_store):
        with patch("src.rag._run_ingestion_job", new=AsyncMock()) as mock_run:
            result = await run_ingestion_job_now("job-succeeded")

    assert result is False
    mock_run.assert_not_awaited()
