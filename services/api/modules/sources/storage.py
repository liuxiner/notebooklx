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

    def load_bytes(self, object_path: str) -> bytes:
        """Load bytes for a previously stored object path."""

    def delete_bytes(self, object_path: str) -> None:
        """Delete a previously stored object path."""


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

    def load_bytes(self, object_path: str) -> bytes:
        target_path = self.root_path / object_path
        try:
            return target_path.read_bytes()
        except FileNotFoundError as exc:
            raise StorageError(str(exc)) from exc

    def delete_bytes(self, object_path: str) -> None:
        target_path = self.root_path / object_path
        try:
            target_path.unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError(str(exc)) from exc


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

    def load_bytes(self, object_path: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=object_path)
            return response["Body"].read()
        except Exception as exc:  # pragma: no cover - boto3 exception graph is broad
            raise StorageError(str(exc)) from exc

    def delete_bytes(self, object_path: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_path)
        except Exception as exc:  # pragma: no cover - boto3 exception graph is broad
            raise StorageError(str(exc)) from exc


def _get_env_value(*names: str) -> str:
    """Return the first non-empty environment variable from the provided names."""
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _build_object_storage_from_env() -> ObjectStorage:
    backend = _get_env_value("SOURCE_STORAGE_BACKEND").lower()
    bucket_name = _get_env_value("SOURCE_STORAGE_BUCKET", "MINIO_BUCKET")

    if backend in {"s3", "minio"} or (not backend and bucket_name):
        if not bucket_name:
            raise StorageError("SOURCE_STORAGE_BUCKET is required when using S3 storage")

        return S3ObjectStorage(
            bucket_name=bucket_name,
            endpoint_url=_get_env_value(
                "SOURCE_STORAGE_ENDPOINT_URL",
                "MINIO_ENDPOINT",
            ) or None,
            region_name=_get_env_value("SOURCE_STORAGE_REGION") or None,
            access_key_id=_get_env_value(
                "SOURCE_STORAGE_ACCESS_KEY_ID",
                "MINIO_ACCESS_KEY",
            ) or None,
            secret_access_key=_get_env_value(
                "SOURCE_STORAGE_SECRET_ACCESS_KEY",
                "MINIO_SECRET_KEY",
            ) or None,
        )

    local_root = Path(
        _get_env_value("SOURCE_STORAGE_ROOT") or str(DEFAULT_LOCAL_STORAGE_ROOT)
    )
    return LocalObjectStorage(local_root)


@lru_cache(maxsize=1)
def get_object_storage() -> ObjectStorage:
    """Build and cache the active object storage backend."""
    return _build_object_storage_from_env()
