"""
Tests for async ingestion pipeline skeleton endpoints.

Feature: 1.4 Async Ingestion Pipeline Skeleton
Slice: enqueue ingestion jobs + query task status
"""
import socket
import subprocess
import time
import uuid
from contextlib import closing
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def created_source(client: TestClient, sample_notebook_data: dict) -> dict:
    """Create a source that can be enqueued for ingestion."""
    notebook_response = client.post("/api/notebooks", json=sample_notebook_data)
    assert notebook_response.status_code == 201
    notebook_id = notebook_response.json()["id"]

    source_response = client.post(
        f"/api/notebooks/{notebook_id}/sources/url",
        json={"url": "https://example.com/ingestion-test", "title": "Queued Source"},
    )
    assert source_response.status_code == 201
    return source_response.json()


class TestEnqueueIngestionTask:
    """Tests for POST /api/sources/{source_id}/ingest."""

    def test_enqueue_ingestion_task_creates_queued_job(
        self,
        client: TestClient,
        created_source: dict,
        db,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """
        AC: Can enqueue ingestion tasks.
        AC: Failed tasks are logged with error details.
        """
        from services.api.modules.ingestion import routes as ingestion_routes
        from services.api.modules.ingestion.models import IngestionJob, IngestionJobStatus

        class RecordingQueue:
            def __init__(self) -> None:
                self.calls = []

            def enqueue_ingestion(self, *, source_id: uuid.UUID, ingestion_job_id: uuid.UUID) -> str:
                self.calls.append(
                    {"source_id": source_id, "ingestion_job_id": ingestion_job_id}
                )
                return "arq-job-123"

        queue = RecordingQueue()
        monkeypatch.setattr(ingestion_routes, "get_ingestion_queue", lambda: queue)

        response = client.post(f"/api/sources/{created_source['id']}/ingest")

        assert response.status_code == 202
        data = response.json()
        assert data["source_id"] == created_source["id"]
        assert data["status"] == "pending"
        assert data["job_status"] == "queued"
        assert data["task_id"] == "arq-job-123"
        assert len(queue.calls) == 1
        assert str(queue.calls[0]["source_id"]) == created_source["id"]

        job = db.query(IngestionJob).filter(
            IngestionJob.source_id == uuid.UUID(created_source["id"])
        ).one()
        assert job.status == IngestionJobStatus.QUEUED
        assert job.task_id == "arq-job-123"

    def test_enqueue_ingestion_task_failure_marks_job_and_source_failed(
        self,
        client: TestClient,
        created_source: dict,
        db,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """
        AC: Failed tasks are logged with error details.
        """
        from services.api.modules.ingestion import routes as ingestion_routes
        from services.api.modules.ingestion.models import IngestionJob, IngestionJobStatus
        from services.api.modules.ingestion.queue import IngestionQueueError
        from services.api.modules.sources.models import Source, SourceStatus

        class FailingQueue:
            def enqueue_ingestion(self, *, source_id: uuid.UUID, ingestion_job_id: uuid.UUID) -> str:
                raise IngestionQueueError("Redis unavailable")

        monkeypatch.setattr(ingestion_routes, "get_ingestion_queue", lambda: FailingQueue())

        response = client.post(f"/api/sources/{created_source['id']}/ingest")

        assert response.status_code == 503
        detail = response.json()["detail"]
        assert detail["error"] == "ingestion_enqueue_failed"

        source = db.query(Source).filter(Source.id == uuid.UUID(created_source["id"])).one()
        assert source.status == SourceStatus.FAILED
        assert source.error_message == "Redis unavailable"

        job = db.query(IngestionJob).filter(IngestionJob.source_id == source.id).one()
        assert job.status == IngestionJobStatus.FAILED
        assert job.error_message == "Redis unavailable"


class TestGetSourceIngestionStatus:
    """Tests for GET /api/sources/{source_id}/status."""

    def test_get_source_ingestion_status_returns_latest_job(
        self, client: TestClient, created_source: dict, db
    ):
        """
        AC: Task status can be queried.
        """
        from services.api.modules.ingestion.models import IngestionJob, IngestionJobStatus
        from services.api.modules.sources.models import Source

        source_id = uuid.UUID(created_source["id"])
        source = db.query(Source).filter(Source.id == source_id).one()

        db.add(
            IngestionJob(
                source_id=source.id,
                status=IngestionJobStatus.RUNNING,
                task_id="arq-running-1",
                progress={"step": "chunking", "percentage": 25},
            )
        )
        db.commit()

        response = client.get(f"/api/sources/{created_source['id']}/status")

        assert response.status_code == 200
        data = response.json()
        assert data["source_id"] == created_source["id"]
        assert data["status"] == "pending"
        assert data["job_status"] == "running"
        assert data["task_id"] == "arq-running-1"
        assert data["progress"] == {"step": "chunking", "percentage": 25}

    def test_get_source_ingestion_status_nonexistent_source_returns_404(
        self, client: TestClient
    ):
        """
        AC: Proper error handling for nonexistent sources.
        """
        response = client.get(f"/api/sources/{uuid.uuid4()}/status")

        assert response.status_code == 404


def _find_free_port() -> int:
    """Ask the OS for an available localhost TCP port."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return sock.getsockname()[1]


@pytest.fixture
def redis_queue_env(tmp_path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Run a disposable Redis server and point the queue config at it."""
    port = _find_free_port()
    redis_url = f"redis://127.0.0.1:{port}/0"
    queue_name = f"notebooklx:test:{uuid.uuid4()}"
    process = subprocess.Popen(
        [
            "redis-server",
            "--bind",
            "127.0.0.1",
            "--port",
            str(port),
            "--save",
            "",
            "--appendonly",
            "no",
            "--dir",
            str(tmp_path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    started = False
    for _ in range(50):
        try:
            with closing(socket.create_connection(("127.0.0.1", port), timeout=0.1)):
                started = True
                break
        except OSError:
            time.sleep(0.1)

    if not started:
        process.terminate()
        process.wait(timeout=5)
        raise RuntimeError("redis-server did not start in time")

    monkeypatch.setenv("REDIS_URL", redis_url)
    monkeypatch.setenv("INGESTION_QUEUE_NAME", queue_name)

    try:
        yield {"redis_url": redis_url, "queue_name": queue_name}
    finally:
        process.terminate()
        process.wait(timeout=5)


class TestIngestionQueueStatus:
    """Tests for GET /api/status/ingestion."""

    def test_ingestion_queue_status_returns_job_counts(
        self, client: TestClient, created_source: dict, db
    ):
        """
        AC: Task status can be queried.
        """
        from services.api.modules.ingestion.models import IngestionJob, IngestionJobStatus

        source_id = uuid.UUID(created_source["id"])
        db.add_all(
            [
                IngestionJob(source_id=source_id, status=IngestionJobStatus.QUEUED),
                IngestionJob(source_id=source_id, status=IngestionJobStatus.RUNNING),
                IngestionJob(source_id=source_id, status=IngestionJobStatus.FAILED),
                IngestionJob(source_id=source_id, status=IngestionJobStatus.COMPLETED),
            ]
        )
        db.commit()

        response = client.get("/api/status/ingestion")

        assert response.status_code == 200
        assert response.json() == {
            "queued_jobs": 1,
            "running_jobs": 1,
            "failed_jobs": 1,
            "completed_jobs": 1,
        }


class TestIngestionHealth:
    """Tests for GET /api/status/ingestion/health."""

    def test_ingestion_health_reports_connected_redis(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        """
        AC: Redis connection is properly configured.
        """
        from services.api.modules.ingestion import routes as ingestion_routes

        class HealthyQueue:
            def ping(self) -> bool:
                return True

        monkeypatch.setattr(ingestion_routes, "get_ingestion_queue", lambda: HealthyQueue())

        response = client.get("/api/status/ingestion/health")

        assert response.status_code == 200
        assert response.json() == {
            "status": "healthy",
            "redis": "connected",
        }


@pytest.mark.skipif(
    os.getenv("NOTEBOOKLX_RUN_REDIS_TESTS") != "1",
    reason="requires local redis socket access",
)
class TestWorkerPipeline:
    """Integration tests for the real Arq worker skeleton."""

    @pytest.mark.asyncio
    async def test_worker_starts_and_processes_queued_job_with_fresh_instance(
        self,
        client: TestClient,
        created_source: dict,
        db,
        redis_queue_env: dict[str, str],
    ):
        """
        AC: Arq worker process starts successfully.
        AC: Tasks are processed asynchronously.
        AC: Worker can be restarted without losing queued tasks.
        AC: Redis connection is properly configured.
        """
        from services.api.tests.conftest import TestingSessionLocal
        from services.worker import main as worker_main

        enqueue_response = client.post(f"/api/sources/{created_source['id']}/ingest")
        assert enqueue_response.status_code == 202
        assert enqueue_response.json()["job_status"] == "queued"

        worker = worker_main.build_worker(
            redis_url=redis_queue_env["redis_url"],
            queue_name=redis_queue_env["queue_name"],
            session_factory=TestingSessionLocal,
            burst=True,
            max_jobs=1,
        )

        completed_jobs = await worker.run_check(max_burst_jobs=1)
        assert completed_jobs == 1

        response = client.get(f"/api/sources/{created_source['id']}/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["job_status"] == "completed"
        assert data["progress"] == {"step": "completed", "percentage": 100}

    @pytest.mark.asyncio
    async def test_worker_failure_marks_job_and_source_failed(
        self,
        client: TestClient,
        created_source: dict,
        redis_queue_env: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ):
        """
        AC: Failed tasks are logged with error details.
        """
        from services.api.tests.conftest import TestingSessionLocal
        from services.worker import main as worker_main

        def fail_ingestion(_source, _job, _db):
            raise RuntimeError("parser crashed")

        monkeypatch.setattr(worker_main, "run_ingestion_pipeline", fail_ingestion)

        enqueue_response = client.post(f"/api/sources/{created_source['id']}/ingest")
        assert enqueue_response.status_code == 202

        worker = worker_main.build_worker(
            redis_url=redis_queue_env["redis_url"],
            queue_name=redis_queue_env["queue_name"],
            session_factory=TestingSessionLocal,
            burst=True,
            max_jobs=1,
        )

        with pytest.raises(Exception):
            await worker.run_check(max_burst_jobs=1)

        response = client.get(f"/api/sources/{created_source['id']}/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["job_status"] == "failed"
        assert data["error_message"] == "parser crashed"
