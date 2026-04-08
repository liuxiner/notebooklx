"""
Tests for async ingestion pipeline skeleton endpoints.

Feature: 1.4 Async Ingestion Pipeline Skeleton
Slice: enqueue ingestion jobs + query task status
"""
import socket
import subprocess
import sys
import time
import types
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


@pytest.fixture
def created_sources(client: TestClient, sample_notebook_data: dict) -> list[dict]:
    """Create multiple sources in one notebook for bulk-ingestion tests."""
    notebook_response = client.post("/api/notebooks", json=sample_notebook_data)
    assert notebook_response.status_code == 201
    notebook_id = notebook_response.json()["id"]

    created: list[dict] = []
    for title in ("Queued Source A", "Queued Source B"):
        source_response = client.post(
            f"/api/notebooks/{notebook_id}/sources/url",
            json={"url": f"https://example.com/{title.lower().replace(' ', '-')}", "title": title},
        )
        assert source_response.status_code == 201
        created.append(source_response.json())

    return created


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

    def test_bulk_enqueue_ingestion_creates_queued_jobs_in_request_order(
        self,
        client: TestClient,
        created_sources: list[dict],
        db,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """
        AC: Ingestion API accepts multiple source IDs in one enqueue request.
        AC: Bulk ingestion response returns one job payload per source in request order.
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
                return f"arq-job-{len(self.calls)}"

        queue = RecordingQueue()
        monkeypatch.setattr(ingestion_routes, "get_ingestion_queue", lambda: queue)

        response = client.post(
            "/api/sources/ingest/batch",
            json={"source_ids": [source["id"] for source in created_sources]},
        )

        assert response.status_code == 202
        data = response.json()
        assert [job["source_id"] for job in data["jobs"]] == [
            source["id"] for source in created_sources
        ]
        assert [job["task_id"] for job in data["jobs"]] == ["arq-job-1", "arq-job-2"]
        assert all(job["job_status"] == "queued" for job in data["jobs"])
        assert len(queue.calls) == 2
        assert [str(call["source_id"]) for call in queue.calls] == [
            source["id"] for source in created_sources
        ]

        jobs = (
            db.query(IngestionJob)
            .order_by(IngestionJob.created_at.asc(), IngestionJob.id.asc())
            .all()
        )
        assert len(jobs) == 2
        assert all(job.status == IngestionJobStatus.QUEUED for job in jobs)

    def test_bulk_enqueue_validates_all_sources_before_enqueuing(
        self,
        client: TestClient,
        created_sources: list[dict],
        db,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """
        AC: Bulk ingestion validates every requested source belongs to the user
        before enqueuing.
        """
        from services.api.modules.ingestion import routes as ingestion_routes
        from services.api.modules.ingestion.models import IngestionJob

        class RecordingQueue:
            def __init__(self) -> None:
                self.calls = []

            def enqueue_ingestion(self, *, source_id: uuid.UUID, ingestion_job_id: uuid.UUID) -> str:
                self.calls.append(
                    {"source_id": source_id, "ingestion_job_id": ingestion_job_id}
                )
                return "unexpected-job"

        queue = RecordingQueue()
        monkeypatch.setattr(ingestion_routes, "get_ingestion_queue", lambda: queue)

        response = client.post(
            "/api/sources/ingest/batch",
            json={"source_ids": [created_sources[0]["id"], str(uuid.uuid4())]},
        )

        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "not_found"
        assert queue.calls == []
        assert db.query(IngestionJob).count() == 0


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

    def test_bulk_status_returns_latest_jobs_in_request_order_and_pending_flag(
        self, client: TestClient, created_sources: list[dict], db
    ):
        """
        AC: Bulk status response returns latest payloads in request order.
        AC: Bulk status indicates whether any requested source is unresolved.
        """
        from services.api.modules.ingestion.models import IngestionJob, IngestionJobStatus
        from services.api.modules.sources.models import Source, SourceStatus

        first_source_id = uuid.UUID(created_sources[0]["id"])
        second_source_id = uuid.UUID(created_sources[1]["id"])

        first_source = db.query(Source).filter(Source.id == first_source_id).one()
        second_source = db.query(Source).filter(Source.id == second_source_id).one()
        first_source.status = SourceStatus.PROCESSING
        second_source.status = SourceStatus.READY

        db.add_all(
            [
                IngestionJob(
                    source_id=first_source.id,
                    status=IngestionJobStatus.RUNNING,
                    task_id="arq-running-1",
                    progress={"step": "embedding", "percentage": 40},
                ),
                IngestionJob(
                    source_id=second_source.id,
                    status=IngestionJobStatus.COMPLETED,
                    task_id="arq-complete-1",
                    progress={"step": "completed", "percentage": 100},
                ),
            ]
        )
        db.commit()

        response = client.post(
            "/api/sources/status/batch",
            json={"source_ids": [created_sources[0]["id"], created_sources[1]["id"]]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["has_pending_sources"] is True
        assert [status["source_id"] for status in data["statuses"]] == [
            created_sources[0]["id"],
            created_sources[1]["id"],
        ]
        assert data["statuses"][0]["job_status"] == "running"
        assert data["statuses"][0]["task_id"] == "arq-running-1"
        assert data["statuses"][1]["job_status"] == "completed"
        assert data["statuses"][1]["task_id"] == "arq-complete-1"

    def test_bulk_status_validates_all_sources_before_returning(
        self, client: TestClient, created_sources: list[dict]
    ):
        """
        AC: Bulk status validates source ownership/nonexistence for every id.
        """
        response = client.post(
            "/api/sources/status/batch",
            json={"source_ids": [created_sources[0]["id"], str(uuid.uuid4())]},
        )

        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "not_found"


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


class TestDeleteIngestionDataRoute:
    def test_delete_ingestion_data_removes_jobs_and_chunks(
        self, client: TestClient, created_source: dict, db
    ):
        """AC: Ingestion data can be cleared for a source."""
        from services.api.modules.chunking.models import SourceChunk
        from services.api.modules.ingestion.models import IngestionJob, IngestionJobStatus
        from services.api.modules.sources.models import Source, SourceStatus

        source_id = uuid.UUID(created_source["id"])
        source = db.query(Source).filter(Source.id == source_id).one()

        db.add_all(
            [
                IngestionJob(
                    source_id=source_id,
                    status=IngestionJobStatus.FAILED,
                    error_message="boom",
                ),
                SourceChunk(
                    source_id=source_id,
                    chunk_index=0,
                    content="chunk",
                    token_count=1,
                    char_start=0,
                    char_end=1,
                    embedding=[0.1, 0.2],
                ),
            ]
        )
        source.status = SourceStatus.FAILED
        source.error_message = "boom"
        db.commit()

        assert (
            db.query(IngestionJob).filter(IngestionJob.source_id == source_id).count() == 1
        )
        assert (
            db.query(SourceChunk).filter(SourceChunk.source_id == source_id).count() == 1
        )

        response = client.delete(f"/api/sources/{created_source['id']}/ingestion")

        assert response.status_code == 204
        assert (
            db.query(IngestionJob).filter(IngestionJob.source_id == source_id).count() == 0
        )
        assert (
            db.query(SourceChunk).filter(SourceChunk.source_id == source_id).count() == 0
        )

        refreshed_source = db.query(Source).filter(Source.id == source_id).one()
        assert refreshed_source.status == SourceStatus.PENDING
        assert refreshed_source.error_message is None


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

            def worker_ping(self) -> bool:
                return True

        monkeypatch.setattr(ingestion_routes, "get_ingestion_queue", lambda: HealthyQueue())

        response = client.get("/api/status/ingestion/health")

        assert response.status_code == 200
        assert response.json() == {
            "status": "healthy",
            "redis": "connected",
            "worker": "connected",
        }

    def test_ingestion_health_reports_missing_worker_when_redis_is_connected(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        """
        AC: Worker health check identifies a queue with no active consumer.
        """
        from services.api.modules.ingestion import routes as ingestion_routes

        class QueueWithoutWorker:
            def ping(self) -> bool:
                return True

            def worker_ping(self) -> bool:
                return False

        monkeypatch.setattr(
            ingestion_routes, "get_ingestion_queue", lambda: QueueWithoutWorker()
        )

        response = client.get("/api/status/ingestion/health")

        assert response.status_code == 200
        assert response.json() == {
            "status": "degraded",
            "redis": "connected",
            "worker": "disconnected",
        }


class TestWorkerBootstrap:
    def test_worker_bootstrap_installs_event_loop_when_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        AC: Worker CLI startup is compatible with Python 3.14 event loop behavior.
        """
        from services.worker import main as worker_main

        installed = {}
        sentinel_loop = object()

        def fail_get_event_loop():
            raise RuntimeError("There is no current event loop in thread 'MainThread'.")

        def build_loop():
            return sentinel_loop

        def install_loop(loop):
            installed["loop"] = loop

        monkeypatch.setattr(worker_main.asyncio, "get_event_loop", fail_get_event_loop)
        monkeypatch.setattr(worker_main.asyncio, "new_event_loop", build_loop)
        monkeypatch.setattr(worker_main.asyncio, "set_event_loop", install_loop)

        worker_main.ensure_main_thread_event_loop()

        assert installed["loop"] is sentinel_loop

    def test_worker_file_loader_uses_shared_object_storage(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        AC: Uploaded file ingestion reads from the same storage backend used by the API.
        """
        from services.worker import main as worker_main

        calls: list[str] = []

        class RecordingStorage:
            def load_bytes(self, object_path: str) -> bytes:
                calls.append(object_path)
                return b"stored-content"

        fake_boto3 = types.SimpleNamespace(
            client=lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("worker should not bypass shared storage")
            )
        )

        monkeypatch.setattr(
            worker_main,
            "get_object_storage",
            lambda: RecordingStorage(),
            raising=False,
        )
        monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

        loader = worker_main._get_file_content_loader({})

        assert loader("notebook/source/upload.txt") == b"stored-content"
        assert calls == ["notebook/source/upload.txt"]


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
