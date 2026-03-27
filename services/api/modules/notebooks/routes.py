"""
API routes for Notebook CRUD operations.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import uuid

from services.api.core.database import get_db
from services.api.modules.notebooks.models import Notebook, User
from services.api.modules.notebooks.schemas import (
    NotebookCreate,
    NotebookUpdate,
    NotebookResponse,
    NotebookListResponse,
    ErrorResponse
)

router = APIRouter(prefix="/api/notebooks", tags=["notebooks"])


# Temporary: Create a default user for testing
# TODO: Replace with actual authentication
def get_current_user_id(db: Session = Depends(get_db)) -> uuid.UUID:
    """Get or create a default user for testing."""
    user = db.query(User).first()
    if not user:
        user = User(email="test@example.com")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user.id


@router.post("", response_model=NotebookResponse, status_code=status.HTTP_201_CREATED)
def create_notebook(
    notebook_data: NotebookCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    """
    Create a new notebook.

    AC: Create notebook with name and optional description
    AC: API responses include creation/update timestamps
    AC: All endpoints return proper HTTP status codes (201)
    """
    # Validate name is not empty (Pydantic handles this, but double-check)
    if not notebook_data.name or not notebook_data.name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": "Notebook name cannot be empty"}
        )

    # Create notebook
    notebook = Notebook(
        user_id=user_id,
        name=notebook_data.name.strip(),
        description=notebook_data.description.strip() if notebook_data.description else None
    )

    db.add(notebook)
    db.commit()
    db.refresh(notebook)

    return notebook


@router.get("", response_model=List[NotebookListResponse])
def list_notebooks(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    """
    List all notebooks for the authenticated user.

    AC: List all notebooks for authenticated user
    AC: Exclude soft-deleted notebooks
    AC: All endpoints return proper HTTP status codes (200)
    """
    notebooks = db.query(Notebook).filter(
        Notebook.user_id == user_id,
        Notebook.deleted_at.is_(None)  # Exclude soft-deleted
    ).all()

    return notebooks


@router.get("/{notebook_id}", response_model=NotebookResponse)
def get_notebook(
    notebook_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    """
    Get a single notebook by ID with all metadata.

    AC: Get single notebook by ID with all metadata
    AC: All endpoints return proper HTTP status codes (200, 404)
    AC: Proper error handling with meaningful error messages
    """
    notebook = db.query(Notebook).filter(
        Notebook.id == notebook_id,
        Notebook.user_id == user_id,
        Notebook.deleted_at.is_(None)  # Exclude soft-deleted
    ).first()

    if not notebook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"Notebook {notebook_id} not found"}
        )

    return notebook


@router.patch("/{notebook_id}", response_model=NotebookResponse)
def update_notebook(
    notebook_id: uuid.UUID,
    update_data: NotebookUpdate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    """
    Update notebook name and/or description.

    AC: Update notebook name and description
    AC: All endpoints return proper HTTP status codes (200, 404, 400)
    AC: Proper error handling with meaningful error messages
    """
    # Find notebook
    notebook = db.query(Notebook).filter(
        Notebook.id == notebook_id,
        Notebook.user_id == user_id,
        Notebook.deleted_at.is_(None)
    ).first()

    if not notebook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"Notebook {notebook_id} not found"}
        )

    # Validate and update fields
    if update_data.name is not None:
        if not update_data.name.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "validation_error", "message": "Notebook name cannot be empty"}
            )
        notebook.name = update_data.name.strip()

    if update_data.description is not None:
        notebook.description = update_data.description.strip() if update_data.description else None

    # Update timestamp manually since SQLite doesn't support onupdate triggers
    notebook.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(notebook)

    return notebook


@router.delete("/{notebook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notebook(
    notebook_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    """
    Soft delete a notebook.

    AC: Delete notebook (soft delete with cascade to sources)
    AC: All endpoints return proper HTTP status codes (204, 404)
    """
    # Find notebook
    notebook = db.query(Notebook).filter(
        Notebook.id == notebook_id,
        Notebook.user_id == user_id,
        Notebook.deleted_at.is_(None)
    ).first()

    if not notebook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"Notebook {notebook_id} not found"}
        )

    # Soft delete
    notebook.deleted_at = datetime.utcnow()
    db.commit()

    return None  # 204 No Content
