"""
Storage backends for uploaded source payloads.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Protocol
import os


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_LOCAL_STORAGE_ROOT = REPO_ROOT / "tmp" / "source_uploads"


class StorageError(Exception):
    """Raised when a source payload cannot be persisted."""


class ObjectStorage(Protocol):
    """Simple protocol for storing bytes by object path."""

    def store_bytes(self, content: bytes, object_path: str, content_type: str) -> str:
        """Persist bytes and return the logical object path."""


class LocalObjectStorage:
    """Filesystem-backed storage used for tests and local fallback."""

    def __init__(self, root_path: Path) -> None:
        self.root_path = root_path

    def store_bytes(self, content: bytes, object_path: str, content_type: str) -> str:
        del content_type  # Local writes do not need MIME metadata.

        target_path = self.root_path / object_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(content)
        return object_path


class S3ObjectStorage:
    """S3-compatible storage for MinIO and cloud object stores."""

    def __init__(
        self,
        bucket_name: str,
        endpoint_url: str | None = None,
        region_name: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        import boto3

        self.bucket_name = bucket_name
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region_name,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    def store_bytes(self, content: bytes, object_path: str, content_type: str) -> str:
        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=object_path,
                Body=content,
                ContentType=content_type,
            )
        except Exception as exc:  # pragma: no cover - boto3 exception graph is broad
            raise StorageError(str(exc)) from exc

        return object_path


def _build_object_storage_from_env() -> ObjectStorage:
    backend = os.getenv("SOURCE_STORAGE_BACKEND", "").strip().lower()
    bucket_name = os.getenv("SOURCE_STORAGE_BUCKET", "").strip()

    if backend == "s3" or bucket_name:
        if not bucket_name:
            raise StorageError("SOURCE_STORAGE_BUCKET is required when using S3 storage")

        return S3ObjectStorage(
            bucket_name=bucket_name,
            endpoint_url=os.getenv("SOURCE_STORAGE_ENDPOINT_URL"),
            region_name=os.getenv("SOURCE_STORAGE_REGION"),
            access_key_id=os.getenv("SOURCE_STORAGE_ACCESS_KEY_ID"),
            secret_access_key=os.getenv("SOURCE_STORAGE_SECRET_ACCESS_KEY"),
        )

    local_root = Path(os.getenv("SOURCE_STORAGE_ROOT", str(DEFAULT_LOCAL_STORAGE_ROOT)))
    return LocalObjectStorage(local_root)


@lru_cache(maxsize=1)
def get_object_storage() -> ObjectStorage:
    """Build and cache the active object storage backend."""
    return _build_object_storage_from_env()
