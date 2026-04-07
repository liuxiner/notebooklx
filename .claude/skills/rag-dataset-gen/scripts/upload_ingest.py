#!/usr/bin/env python3
"""
Upload source files and trigger ingestion pipeline via API.

This script handles the complete workflow of uploading source files
to a notebook and triggering the background ingestion job.
"""
import os
import time
import uuid
import requests
from pathlib import Path
from typing import Dict, Optional, Literal
from dataclasses import dataclass


@dataclass
class IngestionResult:
    """Result of source upload and ingestion."""
    source_id: uuid.UUID
    notebook_id: uuid.UUID
    status: str
    file_path: Optional[str] = None
    error_message: Optional[str] = None


class UploadIngestClient:
    """Client for uploading sources and triggering ingestion."""

    def __init__(
        self,
        api_base_url: str = "http://localhost:8000",
        user_id: Optional[uuid.UUID] = None,
    ):
        """Initialize client with API base URL and optional user ID."""
        self.api_base_url = api_base_url.rstrip("/")
        self.user_id = user_id or uuid.uuid4()  # Default test user
        self.session = requests.Session()

    def upload_pdf(
        self,
        file_path: str,
        notebook_id: uuid.UUID,
        title: Optional[str] = None,
    ) -> IngestionResult:
        """
        Upload a PDF file to a notebook.

        Args:
            file_path: Path to PDF file
            notebook_id: Target notebook UUID
            title: Optional title (defaults to filename)

        Returns:
            IngestionResult with source_id and initial status
        """
        if not Path(file_path).exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        url = f"{self.api_base_url}/api/notebooks/{notebook_id}/sources/upload"

        with open(file_path, "rb") as f:
            files = {"file": (Path(file_path).name, f, "application/pdf")}
            data = {}
            if title:
                data["title"] = title

            response = self.session.post(
                url,
                files=files,
                data=data,
                params={"user_id": str(self.user_id)},
            )

        if response.status_code != 201:
            raise Exception(f"Upload failed: {response.status_code} - {response.text}")

        result_data = response.json()
        return IngestionResult(
            source_id=uuid.UUID(result_data["id"]),
            notebook_id=notebook_id,
            status=result_data["status"],
            file_path=result_data.get("file_path"),
        )

    def upload_text(
        self,
        content: str,
        notebook_id: uuid.UUID,
        title: str = "Text Source",
    ) -> IngestionResult:
        """
        Upload plain text content to a notebook.

        Args:
            content: Text content to upload
            notebook_id: Target notebook UUID
            title: Title for the source

        Returns:
            IngestionResult with source_id and initial status
        """
        url = f"{self.api_base_url}/api/notebooks/{notebook_id}/sources/text"

        payload = {"content": content, "title": title}
        params = {"user_id": str(self.user_id)}

        response = self.session.post(url, json=payload, params=params)

        if response.status_code != 201:
            raise Exception(f"Upload failed: {response.status_code} - {response.text}")

        result_data = response.json()
        return IngestionResult(
            source_id=uuid.UUID(result_data["id"]),
            notebook_id=notebook_id,
            status=result_data["status"],
            file_path=result_data.get("file_path"),
        )

    def trigger_ingestion(self, source_id: uuid.UUID) -> Dict:
        """
        Trigger the ingestion pipeline for a source.

        Args:
            source_id: Source UUID to ingest

        Returns:
            Dict with job_id, task_id, and initial status
        """
        url = f"{self.api_base_url}/api/sources/{source_id}/ingest"
        params = {"user_id": str(self.user_id)}

        response = self.session.post(url, params=params)

        if response.status_code != 202:
            raise Exception(f"Ingestion trigger failed: {response.status_code} - {response.text}")

        return response.json()

    def get_ingestion_status(self, source_id: uuid.UUID) -> Dict:
        """
        Get the current ingestion status for a source.

        Args:
            source_id: Source UUID to check

        Returns:
            Dict with status, progress, error_message, etc.
        """
        url = f"{self.api_base_url}/api/sources/{source_id}/status"
        params = {"user_id": str(self.user_id)}

        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def wait_for_ingestion(
        self,
        source_id: uuid.UUID,
        timeout: int = 120,
        poll_interval: float = 1.0,
    ) -> Dict:
        """
        Wait for ingestion to complete, polling status endpoint.

        Args:
            source_id: Source UUID to wait for
            timeout: Maximum seconds to wait
            poll_interval: Seconds between status checks

        Returns:
            Final status dict when complete or failed
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = self.get_ingestion_status(source_id)

            if status["status"] in ["ready", "completed"]:
                return status
            elif status["status"] == "failed":
                raise Exception(f"Ingestion failed: {status.get('error_message', 'Unknown error')}")

            time.sleep(poll_interval)

        raise TimeoutError(f"Ingestion timed out after {timeout} seconds")

    def upload_and_ingest(
        self,
        file_path: Optional[str] = None,
        content: Optional[str] = None,
        notebook_id: Optional[uuid.UUID] = None,
        title: Optional[str] = None,
        source_type: Literal["pdf", "text"] = "text",
        wait_for_completion: bool = True,
        timeout: int = 120,
    ) -> Dict:
        """
        Complete workflow: upload source and trigger ingestion.

        Args:
            file_path: Path to PDF file (for pdf type)
            content: Text content (for text type)
            notebook_id: Target notebook UUID (creates new if None)
            title: Optional title
            source_type: "pdf" or "text"
            wait_for_completion: Whether to wait for ingestion
            timeout: Max seconds to wait for ingestion

        Returns:
            Dict with source_id, notebook_id, status, and chunks (if completed)
        """
        # Create notebook if not provided
        if notebook_id is None:
            notebook_id = self.create_notebook("RAG Test Notebook")

        # Upload source
        if source_type == "pdf":
            if not file_path:
                raise ValueError("file_path required for pdf type")
            result = self.upload_pdf(file_path, notebook_id, title)
        else:
            if not content:
                raise ValueError("content required for text type")
            result = self.upload_text(content, notebook_id, title or "Text Source")

        # Trigger ingestion
        job_info = self.trigger_ingestion(result.source_id)

        # Wait for completion if requested
        if wait_for_completion:
            final_status = self.wait_for_ingestion(result.source_id, timeout=timeout)
            return {
                "source_id": str(result.source_id),
                "notebook_id": str(notebook_id),
                "status": final_status["status"],
                "job_id": job_info.get("job_id"),
                "error_message": final_status.get("error_message"),
            }

        return {
            "source_id": str(result.source_id),
            "notebook_id": str(notebook_id),
            "status": result.status,
            "job_id": job_info.get("job_id"),
        }

    def create_notebook(self, name: str, description: str = "") -> uuid.UUID:
        """
        Create a new notebook.

        Args:
            name: Notebook name
            description: Optional description

        Returns:
            Created notebook UUID
        """
        url = f"{self.api_base_url}/api/notebooks"
        params = {"user_id": str(self.user_id)}

        payload = {"name": name, "description": description}
        response = self.session.post(url, json=payload, params=params)

        if response.status_code != 201:
            raise Exception(f"Notebook creation failed: {response.status_code} - {response.text}")

        result_data = response.json()
        return uuid.UUID(result_data["id"])


def upload_and_ingest_source(
    content: str,
    source_type: Literal["pdf", "text"] = "text",
    notebook_id: Optional[uuid.UUID] = None,
    api_base_url: str = "http://localhost:8000",
    **kwargs
) -> Dict:
    """
    Convenience function for upload and ingest workflow.

    Args:
        content: File path (for pdf) or text content (for text)
        source_type: "pdf" or "text"
        notebook_id: Target notebook UUID
        api_base_url: API base URL
        **kwargs: Additional arguments (title, timeout, etc.)

    Returns:
        Dict with source_id, notebook_id, status
    """
    client = UploadIngestClient(api_base_url=api_base_url)

    if source_type == "pdf":
        return client.upload_and_ingest(file_path=content, notebook_id=notebook_id, **kwargs)
    else:
        return client.upload_and_ingest(content=content, notebook_id=notebook_id, source_type="text", **kwargs)


def wait_for_ingestion(
    source_id: str,
    api_base_url: str = "http://localhost:8000",
    timeout: int = 120,
) -> Dict:
    """
    Convenience function to wait for ingestion completion.

    Args:
        source_id: Source UUID
        api_base_url: API base URL
        timeout: Max seconds to wait

    Returns:
        Final status dict
    """
    client = UploadIngestClient(api_base_url=api_base_url)
    return client.wait_for_ingestion(uuid.UUID(source_id), timeout=timeout)


if __name__ == "__main__":
    import sys

    # Example usage
    if len(sys.argv) < 2:
        print("Usage: python upload_ingest.py <file_path|content> [notebook_id]")
        sys.exit(1)

    api_url = os.environ.get("API_BASE_URL", "http://localhost:8000")
    path_or_content = sys.argv[1]
    notebook_id = sys.argv[2] if len(sys.argv) > 2 else None

    # Detect if file or content
    if Path(path_or_content).exists():
        result = upload_and_ingest_source(
            content=path_or_content,
            source_type="pdf",
            notebook_id=uuid.UUID(notebook_id) if notebook_id else None,
            api_base_url=api_url,
        )
    else:
        result = upload_and_ingest_source(
            content=path_or_content,
            source_type="text",
            notebook_id=uuid.UUID(notebook_id) if notebook_id else None,
            api_base_url=api_url,
        )

    print(f"✅ Upload complete: {result}")
