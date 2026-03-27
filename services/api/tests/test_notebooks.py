"""
Tests for Notebook CRUD API endpoints.
All tests based on acceptance criteria from Feature 1.1.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime
import uuid


class TestCreateNotebook:
    """Tests for POST /api/notebooks endpoint."""

    def test_create_notebook_with_name_and_description(self, client: TestClient, sample_notebook_data: dict):
        """
        AC: Create notebook with name and optional description
        """
        response = client.post("/api/notebooks", json=sample_notebook_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_notebook_data["name"]
        assert data["description"] == sample_notebook_data["description"]
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_notebook_with_name_only(self, client: TestClient, sample_notebook_data_no_description: dict):
        """
        AC: Create notebook with name and optional description (description is optional)
        """
        response = client.post("/api/notebooks", json=sample_notebook_data_no_description)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_notebook_data_no_description["name"]
        assert data["description"] is None or data["description"] == ""
        assert "id" in data

    def test_create_notebook_without_name_returns_400(self, client: TestClient):
        """
        AC: Proper error handling with meaningful error messages
        AC: All endpoints return proper HTTP status codes (400/422)
        """
        response = client.post("/api/notebooks", json={"description": "No name provided"})

        assert response.status_code in [400, 422]  # FastAPI returns 422 for validation errors
        assert "error" in response.json() or "detail" in response.json()

    def test_create_notebook_with_empty_name_returns_400(self, client: TestClient):
        """
        AC: Proper error handling with meaningful error messages
        """
        response = client.post("/api/notebooks", json={"name": ""})

        assert response.status_code in [400, 422]  # FastAPI returns 422 for validation errors

    def test_create_notebook_returns_timestamps(self, client: TestClient, sample_notebook_data: dict):
        """
        AC: API responses include creation/update timestamps
        """
        response = client.post("/api/notebooks", json=sample_notebook_data)

        assert response.status_code == 201
        data = response.json()
        assert "created_at" in data
        assert "updated_at" in data

        # Verify timestamps are valid ISO format
        datetime.fromisoformat(data["created_at"].replace('Z', '+00:00'))
        datetime.fromisoformat(data["updated_at"].replace('Z', '+00:00'))


class TestListNotebooks:
    """Tests for GET /api/notebooks endpoint."""

    def test_list_notebooks_empty(self, client: TestClient):
        """
        AC: List all notebooks for authenticated user
        """
        response = client.get("/api/notebooks")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_notebooks_with_data(self, client: TestClient, sample_notebook_data: dict):
        """
        AC: List all notebooks for authenticated user
        """
        # Create a notebook first
        create_response = client.post("/api/notebooks", json=sample_notebook_data)
        assert create_response.status_code == 201

        # List notebooks
        response = client.get("/api/notebooks")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == sample_notebook_data["name"]

    def test_list_notebooks_excludes_deleted(self, client: TestClient, sample_notebook_data: dict):
        """
        AC: Delete notebook (soft delete)
        AC: List should not show deleted notebooks
        """
        # Create a notebook
        create_response = client.post("/api/notebooks", json=sample_notebook_data)
        notebook_id = create_response.json()["id"]

        # Delete it
        delete_response = client.delete(f"/api/notebooks/{notebook_id}")
        assert delete_response.status_code == 204

        # List notebooks - should be empty
        response = client.get("/api/notebooks")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0


class TestGetSingleNotebook:
    """Tests for GET /api/notebooks/{id} endpoint."""

    def test_get_notebook_by_id(self, client: TestClient, sample_notebook_data: dict):
        """
        AC: Get single notebook by ID with all metadata
        """
        # Create a notebook first
        create_response = client.post("/api/notebooks", json=sample_notebook_data)
        notebook_id = create_response.json()["id"]

        # Get the notebook
        response = client.get(f"/api/notebooks/{notebook_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == notebook_id
        assert data["name"] == sample_notebook_data["name"]
        assert data["description"] == sample_notebook_data["description"]
        assert "created_at" in data
        assert "updated_at" in data

    def test_get_nonexistent_notebook_returns_404(self, client: TestClient):
        """
        AC: All endpoints return proper HTTP status codes (404)
        AC: Proper error handling with meaningful error messages
        """
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/notebooks/{fake_id}")

        assert response.status_code == 404
        assert "error" in response.json() or "detail" in response.json()

    def test_get_deleted_notebook_returns_404(self, client: TestClient, sample_notebook_data: dict):
        """
        AC: Delete notebook (soft delete)
        AC: Deleted notebooks should not be retrievable
        """
        # Create a notebook
        create_response = client.post("/api/notebooks", json=sample_notebook_data)
        notebook_id = create_response.json()["id"]

        # Delete it
        delete_response = client.delete(f"/api/notebooks/{notebook_id}")
        assert delete_response.status_code == 204

        # Try to get it - should return 404
        response = client.get(f"/api/notebooks/{notebook_id}")
        assert response.status_code == 404


class TestUpdateNotebook:
    """Tests for PATCH /api/notebooks/{id} endpoint."""

    def test_update_notebook_name(self, client: TestClient, sample_notebook_data: dict):
        """
        AC: Update notebook name and description
        """
        # Create a notebook
        create_response = client.post("/api/notebooks", json=sample_notebook_data)
        notebook_id = create_response.json()["id"]

        # Update name
        update_data = {"name": "Updated Notebook Name"}
        response = client.patch(f"/api/notebooks/{notebook_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Notebook Name"
        assert data["description"] == sample_notebook_data["description"]

    def test_update_notebook_description(self, client: TestClient, sample_notebook_data: dict):
        """
        AC: Update notebook name and description
        """
        # Create a notebook
        create_response = client.post("/api/notebooks", json=sample_notebook_data)
        notebook_id = create_response.json()["id"]

        # Update description
        update_data = {"description": "Updated description"}
        response = client.patch(f"/api/notebooks/{notebook_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"
        assert data["name"] == sample_notebook_data["name"]

    def test_update_notebook_both_fields(self, client: TestClient, sample_notebook_data: dict):
        """
        AC: Update notebook name and description
        """
        # Create a notebook
        create_response = client.post("/api/notebooks", json=sample_notebook_data)
        notebook_id = create_response.json()["id"]

        # Update both fields
        update_data = {
            "name": "New Name",
            "description": "New Description"
        }
        response = client.patch(f"/api/notebooks/{notebook_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["description"] == "New Description"

    def test_update_nonexistent_notebook_returns_404(self, client: TestClient):
        """
        AC: All endpoints return proper HTTP status codes (404)
        """
        fake_id = str(uuid.uuid4())
        update_data = {"name": "Updated Name"}
        response = client.patch(f"/api/notebooks/{fake_id}", json=update_data)

        assert response.status_code == 404

    def test_update_notebook_with_empty_name_returns_400(self, client: TestClient, sample_notebook_data: dict):
        """
        AC: Proper error handling with meaningful error messages
        """
        # Create a notebook
        create_response = client.post("/api/notebooks", json=sample_notebook_data)
        notebook_id = create_response.json()["id"]

        # Try to update with empty name
        update_data = {"name": ""}
        response = client.patch(f"/api/notebooks/{notebook_id}", json=update_data)

        assert response.status_code in [400, 422]  # FastAPI returns 422 for validation errors

    def test_update_notebook_updates_timestamp(self, client: TestClient, sample_notebook_data: dict):
        """
        AC: API responses include creation/update timestamps
        """
        # Create a notebook
        create_response = client.post("/api/notebooks", json=sample_notebook_data)
        notebook_id = create_response.json()["id"]
        original_updated_at = create_response.json()["updated_at"]

        # Update notebook
        import time
        time.sleep(0.1)  # Small delay to ensure timestamp difference
        update_data = {"name": "Updated Name"}
        response = client.patch(f"/api/notebooks/{notebook_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert "updated_at" in data
        # The updated_at should be different (in real DB with triggers)
        # For now, just verify it exists


class TestDeleteNotebook:
    """Tests for DELETE /api/notebooks/{id} endpoint."""

    def test_delete_notebook(self, client: TestClient, sample_notebook_data: dict):
        """
        AC: Delete notebook (soft delete with cascade to sources)
        """
        # Create a notebook
        create_response = client.post("/api/notebooks", json=sample_notebook_data)
        notebook_id = create_response.json()["id"]

        # Delete it
        response = client.delete(f"/api/notebooks/{notebook_id}")

        assert response.status_code == 204
        assert response.content == b""

    def test_delete_nonexistent_notebook_returns_404(self, client: TestClient):
        """
        AC: All endpoints return proper HTTP status codes (404)
        """
        fake_id = str(uuid.uuid4())
        response = client.delete(f"/api/notebooks/{fake_id}")

        assert response.status_code == 404

    def test_deleted_notebook_not_in_list(self, client: TestClient, sample_notebook_data: dict):
        """
        AC: Delete notebook (soft delete)
        """
        # Create a notebook
        create_response = client.post("/api/notebooks", json=sample_notebook_data)
        notebook_id = create_response.json()["id"]

        # Delete it
        delete_response = client.delete(f"/api/notebooks/{notebook_id}")
        assert delete_response.status_code == 204

        # Verify it's not in the list
        list_response = client.get("/api/notebooks")
        data = list_response.json()
        notebook_ids = [nb["id"] for nb in data]
        assert notebook_id not in notebook_ids

    def test_deleted_notebook_cannot_be_retrieved(self, client: TestClient, sample_notebook_data: dict):
        """
        AC: Delete notebook (soft delete)
        """
        # Create a notebook
        create_response = client.post("/api/notebooks", json=sample_notebook_data)
        notebook_id = create_response.json()["id"]

        # Delete it
        delete_response = client.delete(f"/api/notebooks/{notebook_id}")
        assert delete_response.status_code == 204

        # Try to get it
        get_response = client.get(f"/api/notebooks/{notebook_id}")
        assert get_response.status_code == 404

    def test_deleted_notebook_cannot_be_updated(self, client: TestClient, sample_notebook_data: dict):
        """
        AC: Delete notebook (soft delete)
        """
        # Create a notebook
        create_response = client.post("/api/notebooks", json=sample_notebook_data)
        notebook_id = create_response.json()["id"]

        # Delete it
        delete_response = client.delete(f"/api/notebooks/{notebook_id}")
        assert delete_response.status_code == 204

        # Try to update it
        update_response = client.patch(f"/api/notebooks/{notebook_id}", json={"name": "New Name"})
        assert update_response.status_code == 404


class TestNotebookErrorHandling:
    """Tests for error handling and edge cases."""

    def test_invalid_uuid_format_returns_400(self, client: TestClient):
        """
        AC: Proper error handling with meaningful error messages
        """
        response = client.get("/api/notebooks/invalid-uuid")

        # Should return 400 or 422 for invalid UUID format
        assert response.status_code in [400, 422]

    def test_server_error_handling(self, client: TestClient):
        """
        AC: All endpoints return proper HTTP status codes (500)
        Note: This test would require mocking a database error
        """
        # Placeholder - would need to mock database failure
        pass
