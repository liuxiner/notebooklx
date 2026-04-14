"""
Tests for Source API endpoints.
All tests based on acceptance criteria from Feature 1.3.

Slice: Sources table schema + Source model + List sources endpoint
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime
import io
import uuid


@pytest.fixture
def created_notebook(client: TestClient, sample_notebook_data: dict) -> dict:
    """Create a notebook and return its data."""
    response = client.post("/api/notebooks", json=sample_notebook_data)
    assert response.status_code == 201
    return response.json()


class TestListSources:
    """Tests for GET /api/notebooks/{notebook_id}/sources endpoint."""

    def test_list_sources_empty(self, client: TestClient, created_notebook: dict):
        """
        AC: List sources for a notebook returns empty list when no sources exist.
        """
        notebook_id = created_notebook["id"]
        response = client.get(f"/api/notebooks/{notebook_id}/sources")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_sources_nonexistent_notebook_returns_404(self, client: TestClient):
        """
        AC: Proper error handling - 404 for nonexistent notebook.
        """
        fake_notebook_id = str(uuid.uuid4())
        response = client.get(f"/api/notebooks/{fake_notebook_id}/sources")

        assert response.status_code == 404

    def test_list_sources_deleted_notebook_returns_404(
        self, client: TestClient, created_notebook: dict
    ):
        """
        AC: Cannot access sources for a deleted notebook.
        """
        notebook_id = created_notebook["id"]

        # Delete the notebook
        delete_response = client.delete(f"/api/notebooks/{notebook_id}")
        assert delete_response.status_code == 204

        # Try to list sources
        response = client.get(f"/api/notebooks/{notebook_id}/sources")
        assert response.status_code == 404


class TestSourceSnapshotSummary:
    """Tests for GET /api/notebooks/{notebook_id}/sources/{source_id}/snapshot."""

    def test_get_source_snapshot_summary_returns_overview_themes_and_keywords(
        self, client: TestClient, created_notebook: dict, db
    ):
        """
        AC: Source snapshot preview exposes only overview, covered themes, and top keywords.
        """
        from services.api.modules.snapshots.models import SourceSnapshot
        from services.api.modules.sources.models import Source, SourceStatus, SourceType

        source = Source(
            notebook_id=uuid.UUID(created_notebook["id"]),
            source_type=SourceType.PDF,
            title="Snapshot-backed source",
            status=SourceStatus.READY,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        snapshot = SourceSnapshot(
            source_id=source.id,
            notebook_id=source.notebook_id,
            schema_version="1.0",
            source_content_hash="abc123",
            generation_method="llm",
            model_name="glm-4.5-air",
            snapshot_data={
                "source_identity": {"source_id": str(source.id)},
                "deterministic": {"content_metrics": {"chunk_count": 3}},
                "semantic": {
                    "content_digest": {
                        "overview": "A concise summary of the source.",
                        "covered_themes": ["Theme A", "Theme B"],
                    },
                    "keywords": [
                        {"term": "keyword-one", "weight": 1.0, "chunk_ids": []},
                        {"term": "keyword-two", "weight": 0.8, "chunk_ids": []},
                    ],
                },
            },
        )
        db.add(snapshot)
        db.commit()

        response = client.get(
            f"/api/notebooks/{created_notebook['id']}/sources/{source.id}/snapshot"
        )

        assert response.status_code == 200
        assert response.json() == {
            "overview": "A concise summary of the source.",
            "covered_themes": ["Theme A", "Theme B"],
            "top_keywords": ["keyword-one", "keyword-two"],
        }

    def test_get_source_snapshot_summary_returns_404_when_missing(
        self, client: TestClient, created_notebook: dict, db
    ):
        """
        AC: Snapshot preview returns not-found when no snapshot is available yet.
        """
        from services.api.modules.sources.models import Source, SourceStatus, SourceType

        source = Source(
            notebook_id=uuid.UUID(created_notebook["id"]),
            source_type=SourceType.URL,
            title="No snapshot yet",
            original_url="https://example.com/no-snapshot",
            status=SourceStatus.READY,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        response = client.get(
            f"/api/notebooks/{created_notebook['id']}/sources/{source.id}/snapshot"
        )

        assert response.status_code == 404
        detail = response.json()["detail"]
        assert detail["error"] == "not_found"
        assert detail["message"] == "Snapshot preview is not available for this source"

    def test_get_source_snapshot_summary_falls_back_when_overview_is_empty(
        self, client: TestClient, created_notebook: dict, db
    ):
        """
        AC: Snapshot preview derives overview from semantic details when stored overview is blank.
        """
        from services.api.modules.snapshots.models import SourceSnapshot
        from services.api.modules.sources.models import Source, SourceStatus, SourceType

        source = Source(
            notebook_id=uuid.UUID(created_notebook["id"]),
            source_type=SourceType.PDF,
            title="Fallback overview source",
            status=SourceStatus.READY,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        snapshot = SourceSnapshot(
            source_id=source.id,
            notebook_id=source.notebook_id,
            schema_version="1.0",
            source_content_hash="fallback123",
            generation_method="llm",
            model_name="glm-4.5-air",
            snapshot_data={
                "source_identity": {"source_id": str(source.id)},
                "deterministic": {"content_metrics": {"chunk_count": 2}},
                "semantic": {
                    "content_digest": {
                        "overview": "",
                        "covered_themes": ["Theme A"],
                        "key_assertions": ["Key assertion one", "Key assertion two"],
                    },
                    "keywords": [
                        {"term": "keyword-one", "weight": 1.0, "chunk_ids": []},
                    ],
                },
            },
        )
        db.add(snapshot)
        db.commit()

        response = client.get(
            f"/api/notebooks/{created_notebook['id']}/sources/{source.id}/snapshot"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["overview"] == "Key assertion one Key assertion two"
        assert data["covered_themes"] == ["Theme A"]
        assert data["top_keywords"] == ["keyword-one"]


class TestCreateURLSource:
    """Tests for POST /api/notebooks/{notebook_id}/sources/url endpoint."""

    def test_create_url_source_returns_pending_source(
        self, client: TestClient, created_notebook: dict
    ):
        """
        AC: Add URL source (validate URL format).
        AC: Return source ID and initial status (pending).
        """
        notebook_id = created_notebook["id"]

        response = client.post(
            f"/api/notebooks/{notebook_id}/sources/url",
            json={
                "title": "Example Article",
                "url": "https://example.com/articles/notebooklx",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"]
        assert data["notebook_id"] == notebook_id
        assert data["source_type"] == "url"
        assert data["title"] == "Example Article"
        assert data["original_url"] == "https://example.com/articles/notebooklx"
        assert data["status"] == "pending"
        assert data["file_path"] is None
        assert data["file_size"] is None

    def test_create_url_source_without_title_uses_url(
        self, client: TestClient, created_notebook: dict
    ):
        """
        AC: URL sources can still be created when only the URL is provided.
        """
        notebook_id = created_notebook["id"]

        response = client.post(
            f"/api/notebooks/{notebook_id}/sources/url",
            json={"url": "https://example.com/resources/123"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "https://example.com/resources/123"
        assert data["original_url"] == "https://example.com/resources/123"
        assert data["status"] == "pending"

    def test_create_url_source_invalid_url_returns_422(
        self, client: TestClient, created_notebook: dict
    ):
        """
        AC: URL format is validated before source creation.
        """
        notebook_id = created_notebook["id"]

        response = client.post(
            f"/api/notebooks/{notebook_id}/sources/url",
            json={"title": "Bad URL", "url": "not-a-url"},
        )

        assert response.status_code == 422

    def test_create_url_source_nonexistent_notebook_returns_404(
        self, client: TestClient
    ):
        """
        AC: Proper error handling for notebook ownership/nonexistence.
        """
        fake_notebook_id = str(uuid.uuid4())

        response = client.post(
            f"/api/notebooks/{fake_notebook_id}/sources/url",
            json={"url": "https://example.com/resource"},
        )

        assert response.status_code == 404


class TestCreateTextSource:
    """Tests for POST /api/notebooks/{notebook_id}/sources/text endpoint."""

    def test_create_text_source_returns_pending_source(
        self, client: TestClient, created_notebook: dict, monkeypatch: pytest.MonkeyPatch
    ):
        """
        AC: Upload plain text content.
        AC: Return source ID and initial status (pending).
        """
        from services.api.modules.sources import routes as source_routes

        class RecordingStorage:
            def __init__(self) -> None:
                self.calls = []

            def store_bytes(self, content: bytes, object_path: str, content_type: str) -> str:
                self.calls.append(
                    {
                        "content": content,
                        "object_path": object_path,
                        "content_type": content_type,
                    }
                )
                return object_path

        storage = RecordingStorage()
        monkeypatch.setattr(source_routes, "get_object_storage", lambda: storage)

        notebook_id = created_notebook["id"]
        payload = {
            "title": "Meeting Notes",
            "content": "Line one\nLine two\nLine three",
        }

        response = client.post(
            f"/api/notebooks/{notebook_id}/sources/text",
            json=payload,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"]
        assert data["notebook_id"] == notebook_id
        assert data["source_type"] == "text"
        assert data["title"] == "Meeting Notes"
        assert data["status"] == "pending"
        assert data["file_size"] == len(payload["content"].encode("utf-8"))
        assert data["file_path"].endswith(".txt")
        assert len(storage.calls) == 1
        assert storage.calls[0]["content"] == payload["content"].encode("utf-8")
        assert storage.calls[0]["content_type"].startswith("text/plain")

    def test_create_text_source_too_large_returns_400(
        self, client: TestClient, created_notebook: dict
    ):
        """
        AC: Text uploads enforce the 10MB size limit.
        """
        notebook_id = created_notebook["id"]
        oversized_content = "a" * ((10 * 1024 * 1024) + 1)

        response = client.post(
            f"/api/notebooks/{notebook_id}/sources/text",
            json={"title": "Oversized", "content": oversized_content},
        )

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["error"] == "validation_error"

    def test_create_text_source_nonexistent_notebook_returns_404(
        self, client: TestClient
    ):
        """
        AC: Text uploads honor notebook ownership and existence checks.
        """
        fake_notebook_id = str(uuid.uuid4())

        response = client.post(
            f"/api/notebooks/{fake_notebook_id}/sources/text",
            json={"title": "Notes", "content": "Some content"},
        )

        assert response.status_code == 404


class TestUploadSourceFile:
    """Tests for POST /api/notebooks/{notebook_id}/sources/upload endpoint."""

    def test_upload_pdf_source_returns_pending_source(
        self, client: TestClient, created_notebook: dict, monkeypatch: pytest.MonkeyPatch
    ):
        """
        AC: Upload PDF file (max 50MB).
        AC: Store original file and return pending source metadata.
        """
        from services.api.modules.sources import routes as source_routes

        class RecordingStorage:
            def __init__(self) -> None:
                self.calls = []

            def store_bytes(self, content: bytes, object_path: str, content_type: str) -> str:
                self.calls.append(
                    {
                        "content": content,
                        "object_path": object_path,
                        "content_type": content_type,
                    }
                )
                return object_path

        storage = RecordingStorage()
        monkeypatch.setattr(source_routes, "get_object_storage", lambda: storage)

        notebook_id = created_notebook["id"]
        file_bytes = b"%PDF-1.7 sample pdf bytes"

        response = client.post(
            f"/api/notebooks/{notebook_id}/sources/upload",
            data={"title": "Quarterly Report"},
            files={"file": ("report.pdf", io.BytesIO(file_bytes), "application/pdf")},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["source_type"] == "pdf"
        assert data["title"] == "Quarterly Report"
        assert data["status"] == "pending"
        assert data["file_size"] == len(file_bytes)
        assert data["file_path"].endswith("/report.pdf")
        assert len(storage.calls) == 1
        assert storage.calls[0]["content"] == file_bytes
        assert storage.calls[0]["content_type"] == "application/pdf"

    @pytest.mark.parametrize(
        ("filename", "content_type", "expected_source_type"),
        [
            ("notes.txt", "text/plain", "text"),
            (
                "agenda.docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "text",
            ),
        ],
    )
    def test_upload_supported_file_types_are_accepted(
        self,
        client: TestClient,
        created_notebook: dict,
        monkeypatch: pytest.MonkeyPatch,
        filename: str,
        content_type: str,
        expected_source_type: str,
    ):
        """
        AC: Support multiple file types (PDF, TXT, DOCX).
        AC: Proper MIME type validation for allowed document types.
        """
        from services.api.modules.sources import routes as source_routes

        class RecordingStorage:
            def store_bytes(self, _content: bytes, object_path: str, _content_type: str) -> str:
                return object_path

        monkeypatch.setattr(source_routes, "get_object_storage", lambda: RecordingStorage())

        notebook_id = created_notebook["id"]

        response = client.post(
            f"/api/notebooks/{notebook_id}/sources/upload",
            files={"file": (filename, io.BytesIO(b"sample"), content_type)},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["source_type"] == expected_source_type
        assert data["status"] == "pending"
        assert data["file_path"].endswith(f"/{filename}")

    def test_upload_defaults_title_to_full_filename_stem_without_stripping_unicode(
        self, client: TestClient, created_notebook: dict, monkeypatch: pytest.MonkeyPatch
    ):
        """
        AC: Default upload title keeps the original filename text except the extension.
        AC: Unicode and special characters are preserved for file-backed source titles.
        """
        from services.api.modules.sources import routes as source_routes

        class RecordingStorage:
            def store_bytes(self, _content: bytes, object_path: str, _content_type: str) -> str:
                return object_path

        monkeypatch.setattr(source_routes, "get_object_storage", lambda: RecordingStorage())

        notebook_id = created_notebook["id"]
        filename = "2026预算（终版） #A&B?.pdf"

        response = client.post(
            f"/api/notebooks/{notebook_id}/sources/upload",
            files={"file": (filename, io.BytesIO(b"%PDF"), "application/pdf")},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "2026预算（终版） #A&B?"
        assert data["file_path"].endswith(f"/{filename}")

    def test_upload_invalid_mime_type_returns_400(
        self, client: TestClient, created_notebook: dict
    ):
        """
        AC: Unsupported MIME types are rejected.
        """
        notebook_id = created_notebook["id"]

        response = client.post(
            f"/api/notebooks/{notebook_id}/sources/upload",
            files={"file": ("image.png", io.BytesIO(b"png"), "image/png")},
        )

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["error"] == "validation_error"

    def test_upload_file_too_large_returns_400(
        self, client: TestClient, created_notebook: dict
    ):
        """
        AC: File size limits are enforced for uploaded documents.
        """
        notebook_id = created_notebook["id"]
        oversized_file = b"a" * ((10 * 1024 * 1024) + 1)

        response = client.post(
            f"/api/notebooks/{notebook_id}/sources/upload",
            files={"file": ("too-large.txt", io.BytesIO(oversized_file), "text/plain")},
        )

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["error"] == "validation_error"

    def test_upload_storage_failure_marks_source_failed(
        self,
        client: TestClient,
        created_notebook: dict,
        db,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """
        AC: Failed uploads persist an error state and return a server error.
        """
        from services.api.modules.sources import routes as source_routes
        from services.api.modules.sources.models import Source, SourceStatus
        from services.api.modules.sources.storage import StorageError

        class FailingStorage:
            def store_bytes(self, _content: bytes, _object_path: str, _content_type: str) -> str:
                raise StorageError("MinIO unavailable")

        monkeypatch.setattr(source_routes, "get_object_storage", lambda: FailingStorage())

        notebook_id = created_notebook["id"]

        response = client.post(
            f"/api/notebooks/{notebook_id}/sources/upload",
            files={"file": ("report.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
        )

        assert response.status_code == 500
        detail = response.json()["detail"]
        assert detail["error"] == "upload_failed"

        source = db.query(Source).filter(Source.notebook_id == uuid.UUID(notebook_id)).one()
        assert source.status == SourceStatus.FAILED
        assert source.error_message == "MinIO unavailable"


class TestBulkUploadSourceFiles:
    """Tests for POST /api/notebooks/{notebook_id}/sources/upload/batch endpoint."""

    def test_upload_multiple_files_returns_created_sources_in_order(
        self, client: TestClient, created_notebook: dict, monkeypatch: pytest.MonkeyPatch
    ):
        """
        AC: Sources API creates one source record per uploaded file and returns
        created sources in request order.
        AC: Bulk upload defaults each created source title to the filename stem.
        """
        from services.api.modules.sources import routes as source_routes

        class RecordingStorage:
            def __init__(self) -> None:
                self.calls = []

            def store_bytes(self, content: bytes, object_path: str, content_type: str) -> str:
                self.calls.append(
                    {
                        "content": content,
                        "object_path": object_path,
                        "content_type": content_type,
                    }
                )
                return object_path

        storage = RecordingStorage()
        monkeypatch.setattr(source_routes, "get_object_storage", lambda: storage)

        notebook_id = created_notebook["id"]
        pdf_bytes = b"%PDF batch one"
        txt_bytes = b"batch notes"

        response = client.post(
            f"/api/notebooks/{notebook_id}/sources/upload/batch",
            files=[
                ("files", ("brief.pdf", io.BytesIO(pdf_bytes), "application/pdf")),
                ("files", ("notes.txt", io.BytesIO(txt_bytes), "text/plain")),
            ],
        )

        assert response.status_code == 201
        data = response.json()

        assert [item["title"] for item in data] == ["brief", "notes"]
        assert [item["source_type"] for item in data] == ["pdf", "text"]
        assert [item["status"] for item in data] == ["pending", "pending"]
        assert data[0]["file_path"].endswith("/brief.pdf")
        assert data[1]["file_path"].endswith("/notes.txt")
        assert len(storage.calls) == 2
        assert storage.calls[0]["content"] == pdf_bytes
        assert storage.calls[1]["content"] == txt_bytes

    def test_bulk_upload_preserves_unicode_and_special_characters_in_default_titles(
        self, client: TestClient, created_notebook: dict, monkeypatch: pytest.MonkeyPatch
    ):
        """
        AC: Bulk upload preserves the original filename stem for mixed-language names.
        """
        from services.api.modules.sources import routes as source_routes

        class RecordingStorage:
            def store_bytes(self, _content: bytes, object_path: str, _content_type: str) -> str:
                return object_path

        monkeypatch.setattr(source_routes, "get_object_storage", lambda: RecordingStorage())

        notebook_id = created_notebook["id"]
        filename = "第2章 研发总结（v1.0） #A&B?.txt"

        response = client.post(
            f"/api/notebooks/{notebook_id}/sources/upload/batch",
            files=[("files", (filename, io.BytesIO(b"batch notes"), "text/plain"))],
        )

        assert response.status_code == 201
        data = response.json()
        assert [item["title"] for item in data] == ["第2章 研发总结（v1.0） #A&B?"]
        assert data[0]["file_path"].endswith(f"/{filename}")

    def test_bulk_upload_rejects_mixed_unsupported_files_without_persisting_sources(
        self,
        client: TestClient,
        created_notebook: dict,
        db,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """
        AC: Bulk upload rejects unsupported file types while preserving
        per-file validation rules.
        """
        from services.api.modules.sources import routes as source_routes
        from services.api.modules.sources.models import Source

        class RecordingStorage:
            def __init__(self) -> None:
                self.calls = []

            def store_bytes(self, content: bytes, object_path: str, content_type: str) -> str:
                self.calls.append(
                    {
                        "content": content,
                        "object_path": object_path,
                        "content_type": content_type,
                    }
                )
                return object_path

        storage = RecordingStorage()
        monkeypatch.setattr(source_routes, "get_object_storage", lambda: storage)

        notebook_id = created_notebook["id"]

        response = client.post(
            f"/api/notebooks/{notebook_id}/sources/upload/batch",
            files=[
                ("files", ("brief.pdf", io.BytesIO(b"%PDF"), "application/pdf")),
                ("files", ("diagram.png", io.BytesIO(b"png"), "image/png")),
            ],
        )

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["error"] == "validation_error"
        assert storage.calls == []
        assert (
            db.query(Source)
            .filter(Source.notebook_id == uuid.UUID(notebook_id))
            .count()
            == 0
        )

    def test_bulk_upload_rejects_more_than_fifty_files(
        self,
        client: TestClient,
        created_notebook: dict,
    ):
        """
        AC: Batch upload supports at most 50 files in a single request.
        """
        notebook_id = created_notebook["id"]
        files = [
            ("files", (f"doc-{index}.txt", io.BytesIO(b"payload"), "text/plain"))
            for index in range(51)
        ]

        response = client.post(
            f"/api/notebooks/{notebook_id}/sources/upload/batch",
            files=files,
        )

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["error"] == "validation_error"
        assert detail["message"] == "Batch upload supports up to 50 files per request."


class TestDeleteSource:
    """Tests for DELETE /api/notebooks/{notebook_id}/sources/{source_id} endpoint."""

    def test_delete_source_returns_204_and_removes_record(
        self, client: TestClient, created_notebook: dict, db, monkeypatch: pytest.MonkeyPatch
    ):
        """
        AC: Deleting a source removes it from the notebook and returns 204.
        AC: File-backed sources remove their stored payload.
        """
        from services.api.modules.sources import cleanup as source_cleanup
        from services.api.modules.sources.models import Source, SourceStatus, SourceType

        class RecordingStorage:
            def __init__(self) -> None:
                self.deleted_paths = []

            def delete_bytes(self, object_path: str) -> None:
                self.deleted_paths.append(object_path)

        storage = RecordingStorage()
        monkeypatch.setattr(source_cleanup, "get_object_storage", lambda: storage)

        source = Source(
            notebook_id=uuid.UUID(created_notebook["id"]),
            source_type=SourceType.TEXT,
            title="Source to delete",
            file_path="notebook/source-to-delete.txt",
            file_size=128,
            status=SourceStatus.READY,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        response = client.delete(
            f"/api/notebooks/{created_notebook['id']}/sources/{source.id}"
        )

        assert response.status_code == 204
        assert response.content == b""
        assert storage.deleted_paths == ["notebook/source-to-delete.txt"]
        assert db.query(Source).filter(Source.id == source.id).first() is None

    def test_delete_source_removes_derived_records(
        self, client: TestClient, created_notebook: dict, db
    ):
        """
        AC: Deleting a source cascades to chunks, snapshots, and ingestion jobs.
        """
        from services.api.modules.chunking.models import SourceChunk
        from services.api.modules.ingestion.models import IngestionJob, IngestionJobStatus
        from services.api.modules.snapshots.models import SourceSnapshot
        from services.api.modules.sources.models import Source, SourceStatus, SourceType

        source = Source(
            notebook_id=uuid.UUID(created_notebook["id"]),
            source_type=SourceType.URL,
            title="Derived records source",
            original_url="https://example.com/delete-me",
            status=SourceStatus.READY,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        chunk = SourceChunk(
            source_id=source.id,
            chunk_index=0,
            content="Chunk content",
            token_count=2,
            char_start=0,
            char_end=13,
        )
        job = IngestionJob(
            source_id=source.id,
            status=IngestionJobStatus.COMPLETED,
            progress={"step": "completed"},
        )
        snapshot = SourceSnapshot(
            source_id=source.id,
            notebook_id=source.notebook_id,
            schema_version="test-v1",
            source_content_hash="abc123",
            generation_method="heuristic",
            snapshot_data={
                "source_identity": {"source_id": str(source.id)},
                "deterministic": {"content_metrics": {"chunk_count": 1}},
                "semantic": {"content_digest": {"overview": "Overview"}, "keywords": []},
            },
        )
        db.add_all([chunk, job, snapshot])
        db.commit()

        response = client.delete(
            f"/api/notebooks/{created_notebook['id']}/sources/{source.id}"
        )

        assert response.status_code == 204
        assert db.query(Source).filter(Source.id == source.id).first() is None
        assert db.query(SourceChunk).filter(SourceChunk.source_id == source.id).count() == 0
        assert db.query(SourceSnapshot).filter(SourceSnapshot.source_id == source.id).count() == 0
        assert db.query(IngestionJob).filter(IngestionJob.source_id == source.id).count() == 0

    def test_delete_source_without_file_path_skips_storage_cleanup(
        self, client: TestClient, created_notebook: dict, db, monkeypatch: pytest.MonkeyPatch
    ):
        """
        AC: Non-file sources delete cleanly without storage calls.
        """
        from services.api.modules.sources import cleanup as source_cleanup
        from services.api.modules.sources.models import Source, SourceStatus, SourceType

        class RecordingStorage:
            def __init__(self) -> None:
                self.deleted_paths = []

            def delete_bytes(self, object_path: str) -> None:
                self.deleted_paths.append(object_path)

        storage = RecordingStorage()
        monkeypatch.setattr(source_cleanup, "get_object_storage", lambda: storage)

        source = Source(
            notebook_id=uuid.UUID(created_notebook["id"]),
            source_type=SourceType.URL,
            title="URL source",
            original_url="https://example.com",
            status=SourceStatus.PENDING,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        response = client.delete(
            f"/api/notebooks/{created_notebook['id']}/sources/{source.id}"
        )

        assert response.status_code == 204
        assert storage.deleted_paths == []

    def test_delete_source_nonexistent_notebook_returns_404(self, client: TestClient):
        """
        AC: Notebook ownership and existence are validated before deletion.
        """
        response = client.delete(
            f"/api/notebooks/{uuid.uuid4()}/sources/{uuid.uuid4()}"
        )

        assert response.status_code == 404

    def test_delete_source_nonexistent_source_returns_404(
        self, client: TestClient, created_notebook: dict
    ):
        """
        AC: Missing sources return a not-found error.
        """
        response = client.delete(
            f"/api/notebooks/{created_notebook['id']}/sources/{uuid.uuid4()}"
        )

        assert response.status_code == 404


class TestObjectStorageConfiguration:
    """Tests for environment-driven object storage selection."""

    def test_s3_load_bytes_retries_retryable_gateway_errors(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        AC: Object storage reads retry transient 5xx gateway failures.
        """
        from services.api.modules.sources import storage as source_storage

        class FakeBody:
            def read(self) -> bytes:
                return b"ok"

        class FakeClient:
            def __init__(self) -> None:
                self.calls = 0

            def get_object(self, **_kwargs):
                self.calls += 1
                if self.calls < 3:
                    raise Exception("An error occurred (502) when calling the GetObject operation")
                return {"Body": FakeBody()}

        storage = source_storage.S3ObjectStorage(bucket_name="test-bucket")
        storage.client = FakeClient()
        sleeps: list[float] = []

        monkeypatch.setattr(source_storage, "DEFAULT_STORAGE_READ_MAX_ATTEMPTS", 3)
        monkeypatch.setattr(source_storage, "DEFAULT_STORAGE_READ_RETRY_BASE_SECONDS", 0.2)
        monkeypatch.setattr(source_storage.time, "sleep", lambda seconds: sleeps.append(seconds))

        content = storage.load_bytes("path/to/object.pdf")

        assert content == b"ok"
        assert storage.client.calls == 3
        assert sleeps == [0.2, 0.4]

    def test_upload_fails_when_implicit_minio_is_unavailable(
        self,
        client: TestClient,
        created_notebook: dict,
        monkeypatch: pytest.MonkeyPatch,
        db,
    ) -> None:
        """
        Bug: uploads must fail when implicit MinIO config is present but the
        MinIO/S3 backend itself is unavailable.
        """
        from services.api.modules.sources import storage as source_storage
        from services.api.modules.sources.models import Source, SourceStatus

        class FailingS3Storage:
            def __init__(
                self,
                bucket_name: str,
                endpoint_url: str | None = None,
                region_name: str | None = None,
                access_key_id: str | None = None,
                secret_access_key: str | None = None,
            ) -> None:
                del bucket_name, endpoint_url, region_name, access_key_id, secret_access_key

            def store_bytes(self, _content: bytes, _object_path: str, _content_type: str) -> str:
                raise source_storage.StorageError("Could not connect to the endpoint URL")

            def load_bytes(self, _object_path: str) -> bytes:
                raise source_storage.StorageError("Could not connect to the endpoint URL")

            def delete_bytes(self, _object_path: str) -> None:
                raise source_storage.StorageError("Could not connect to the endpoint URL")

        monkeypatch.delenv("SOURCE_STORAGE_BACKEND", raising=False)
        monkeypatch.delenv("SOURCE_STORAGE_BUCKET", raising=False)
        monkeypatch.delenv("SOURCE_STORAGE_ENDPOINT_URL", raising=False)
        monkeypatch.delenv("SOURCE_STORAGE_REGION", raising=False)
        monkeypatch.delenv("SOURCE_STORAGE_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("SOURCE_STORAGE_SECRET_ACCESS_KEY", raising=False)
        monkeypatch.setenv("MINIO_BUCKET", "notebooklx")
        monkeypatch.setenv("MINIO_ENDPOINT", "http://localhost:9000")
        monkeypatch.setenv("MINIO_ACCESS_KEY", "minioadmin")
        monkeypatch.setenv("MINIO_SECRET_KEY", "minioadmin")
        monkeypatch.setattr(source_storage, "S3ObjectStorage", FailingS3Storage)
        source_storage.get_object_storage.cache_clear()

        try:
            notebook_id = created_notebook["id"]
            response = client.post(
                f"/api/notebooks/{notebook_id}/sources/upload",
                files={"file": ("strict-minio.pdf", io.BytesIO(b"%PDF-1.7 strict minio"), "application/pdf")},
            )
        finally:
            source_storage.get_object_storage.cache_clear()

        assert response.status_code == 500
        detail = response.json()["detail"]
        assert detail["error"] == "upload_failed"

        source = db.query(Source).filter(Source.notebook_id == uuid.UUID(notebook_id)).one()
        assert source.status == SourceStatus.FAILED
        assert source.error_message == "Could not connect to the endpoint URL"

    def test_minio_env_uses_strict_s3_storage_backend(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        AC: Implicit local MinIO configuration resolves directly to the shared
        S3-compatible backend with no local fallback wrapper.
        """
        from services.api.modules.sources import storage as source_storage

        captured: dict[str, str | None] = {}

        class RecordingS3Storage:
            def __init__(
                self,
                bucket_name: str,
                endpoint_url: str | None = None,
                region_name: str | None = None,
                access_key_id: str | None = None,
                secret_access_key: str | None = None,
            ) -> None:
                captured.update(
                    {
                        "bucket_name": bucket_name,
                        "endpoint_url": endpoint_url,
                        "region_name": region_name,
                        "access_key_id": access_key_id,
                        "secret_access_key": secret_access_key,
                    }
                )

        monkeypatch.delenv("SOURCE_STORAGE_BACKEND", raising=False)
        monkeypatch.delenv("SOURCE_STORAGE_BUCKET", raising=False)
        monkeypatch.delenv("SOURCE_STORAGE_ENDPOINT_URL", raising=False)
        monkeypatch.delenv("SOURCE_STORAGE_REGION", raising=False)
        monkeypatch.delenv("SOURCE_STORAGE_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("SOURCE_STORAGE_SECRET_ACCESS_KEY", raising=False)
        monkeypatch.setenv("MINIO_BUCKET", "notebooklx")
        monkeypatch.setenv("MINIO_ENDPOINT", "http://localhost:9000")
        monkeypatch.setenv("MINIO_ACCESS_KEY", "minioadmin")
        monkeypatch.setenv("MINIO_SECRET_KEY", "minioadmin")
        monkeypatch.setattr(source_storage, "S3ObjectStorage", RecordingS3Storage)

        storage = source_storage._build_object_storage_from_env()

        assert isinstance(storage, RecordingS3Storage)
        assert captured == {
            "bucket_name": "notebooklx",
            "endpoint_url": "http://localhost:9000",
            "region_name": None,
            "access_key_id": "minioadmin",
            "secret_access_key": "minioadmin",
        }

    def test_explicit_minio_backend_uses_strict_s3_storage_backend(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        AC: Explicit MinIO/S3 backend selection remains strict and does not
        silently switch to local storage.
        """
        from services.api.modules.sources import storage as source_storage

        class RecordingS3Storage:
            def __init__(
                self,
                bucket_name: str,
                endpoint_url: str | None = None,
                region_name: str | None = None,
                access_key_id: str | None = None,
                secret_access_key: str | None = None,
            ) -> None:
                del bucket_name, endpoint_url, region_name, access_key_id, secret_access_key

        monkeypatch.setenv("SOURCE_STORAGE_BACKEND", "minio")
        monkeypatch.setenv("MINIO_BUCKET", "notebooklx")
        monkeypatch.setenv("MINIO_ENDPOINT", "http://localhost:9000")
        monkeypatch.setattr(source_storage, "S3ObjectStorage", RecordingS3Storage)

        storage = source_storage._build_object_storage_from_env()

        assert isinstance(storage, RecordingS3Storage)

    def test_s3_client_disables_proxies_for_local_minio_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        AC: Local MinIO endpoint bypasses HTTP proxy settings.
        """
        from services.api.modules.sources import storage as source_storage

        captured: dict[str, object] = {}

        class FakeBoto3:
            @staticmethod
            def client(service_name: str, **kwargs):
                captured["service_name"] = service_name
                captured.update(kwargs)
                return object()

        monkeypatch.setitem(__import__("sys").modules, "boto3", FakeBoto3)

        source_storage.S3ObjectStorage(
            bucket_name="notebooklx",
            endpoint_url="http://localhost:9000",
            access_key_id="minioadmin",
            secret_access_key="minioadmin",
        )

        assert captured["service_name"] == "s3"
        assert "config" in captured
        assert getattr(captured["config"], "proxies", None) == {}


class TestSourceModel:
    """Tests to verify Source model schema and fields."""

    def test_source_has_required_fields(self, db):
        """
        AC: Source model has all required fields:
        - id (UUID)
        - notebook_id (foreign key)
        - source_type (enum: pdf, url, text, youtube, audio, gdocs)
        - title (string)
        - status (enum: pending, processing, ready, failed)
        - created_at, updated_at timestamps
        """
        from services.api.modules.sources.models import Source, SourceType, SourceStatus
        from services.api.modules.notebooks.models import Notebook, User

        # Create a user and notebook first
        user = User(email="test-source@example.com")
        db.add(user)
        db.commit()

        notebook = Notebook(user_id=user.id, name="Test Notebook for Sources")
        db.add(notebook)
        db.commit()

        # Create a source
        source = Source(
            notebook_id=notebook.id,
            source_type=SourceType.TEXT,
            title="Test Source",
            status=SourceStatus.PENDING,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        # Verify fields
        assert source.id is not None
        assert isinstance(source.id, uuid.UUID)
        assert source.notebook_id == notebook.id
        assert source.source_type == SourceType.TEXT
        assert source.title == "Test Source"
        assert source.status == SourceStatus.PENDING
        assert source.created_at is not None
        assert source.updated_at is not None

    def test_source_type_enum_values(self):
        """
        AC: Source type enum has all expected values.
        """
        from services.api.modules.sources.models import SourceType

        assert hasattr(SourceType, "PDF")
        assert hasattr(SourceType, "URL")
        assert hasattr(SourceType, "TEXT")
        assert hasattr(SourceType, "YOUTUBE")
        assert hasattr(SourceType, "AUDIO")
        assert hasattr(SourceType, "GDOCS")

    def test_source_status_enum_values(self):
        """
        AC: Source status enum has all expected values.
        """
        from services.api.modules.sources.models import SourceStatus

        assert hasattr(SourceStatus, "PENDING")
        assert hasattr(SourceStatus, "PROCESSING")
        assert hasattr(SourceStatus, "READY")
        assert hasattr(SourceStatus, "FAILED")

    def test_source_optional_fields(self, db):
        """
        AC: Source has optional fields:
        - original_url (string, optional)
        - file_path (string, optional)
        - file_size (integer, optional)
        - error_message (text, optional)
        """
        from services.api.modules.sources.models import Source, SourceType, SourceStatus
        from services.api.modules.notebooks.models import Notebook, User

        # Create a user and notebook first
        user = User(email="test-source-optional@example.com")
        db.add(user)
        db.commit()

        notebook = Notebook(user_id=user.id, name="Test Notebook")
        db.add(notebook)
        db.commit()

        # Create source with optional fields
        source = Source(
            notebook_id=notebook.id,
            source_type=SourceType.PDF,
            title="PDF Source",
            status=SourceStatus.READY,
            original_url="https://example.com/doc.pdf",
            file_path="/storage/doc.pdf",
            file_size=1024000,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        assert source.original_url == "https://example.com/doc.pdf"
        assert source.file_path == "/storage/doc.pdf"
        assert source.file_size == 1024000
        assert source.error_message is None

    def test_source_error_message_on_failure(self, db):
        """
        AC: Failed sources have error_message populated.
        """
        from services.api.modules.sources.models import Source, SourceType, SourceStatus
        from services.api.modules.notebooks.models import Notebook, User

        user = User(email="test-source-error@example.com")
        db.add(user)
        db.commit()

        notebook = Notebook(user_id=user.id, name="Test Notebook")
        db.add(notebook)
        db.commit()

        source = Source(
            notebook_id=notebook.id,
            source_type=SourceType.URL,
            title="Failed URL Source",
            status=SourceStatus.FAILED,
            error_message="Connection timeout after 30 seconds",
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        assert source.status == SourceStatus.FAILED
        assert source.error_message == "Connection timeout after 30 seconds"

    def test_source_cascade_delete_with_notebook(self, db):
        """
        AC: Sources are deleted when notebook is deleted (cascade).
        """
        from sqlalchemy import delete
        from services.api.modules.sources.models import Source, SourceType, SourceStatus
        from services.api.modules.notebooks.models import Notebook, User

        user = User(email="test-cascade@example.com")
        db.add(user)
        db.commit()

        notebook = Notebook(user_id=user.id, name="Notebook to delete")
        db.add(notebook)
        db.commit()
        notebook_id = notebook.id

        source = Source(
            notebook_id=notebook.id,
            source_type=SourceType.TEXT,
            title="Source to be cascaded",
            status=SourceStatus.READY,
        )
        db.add(source)
        db.commit()
        source_id = source.id

        # Use SQLAlchemy's typed delete so UUID binding matches the backend.
        db.execute(delete(Notebook).where(Notebook.id == notebook_id))
        db.commit()
        db.expire_all()

        # Verify source is also deleted
        deleted_source = db.query(Source).filter(Source.id == source_id).first()
        assert deleted_source is None
