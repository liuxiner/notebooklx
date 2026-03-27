"""
Main FastAPI application for NotebookLX.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.core.database import initialize_database
from services.api.modules.notebooks.routes import router as notebooks_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize local development database state before serving requests."""
    initialize_database()
    yield


# Create FastAPI app
app = FastAPI(
    title="NotebookLX API",
    description="Source-grounded notebook knowledge workspace",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(notebooks_router)


@app.get("/")
def root():
    """Root endpoint."""
    return {"message": "Welcome to NotebookLX API"}


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
