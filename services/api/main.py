"""
Main FastAPI application for NotebookLX.
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Try to load .env from the repository root
    env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(env_path)
    logging.info(f"Loaded environment variables from {env_path}")
except ImportError:
    logging.warning("python-dotenv not installed, environment variables must be set manually")
except Exception as e:
    logging.warning(f"Could not load .env file: {e}")

from services.api.core.database import initialize_database
from services.api.modules.chat.routes import router as chat_router
from services.api.modules.citations.routes import router as citations_router
from services.api.modules.ingestion.routes import router as ingestion_router
from services.api.modules.notebooks.routes import router as notebooks_router
from services.api.modules.sources.routes import router as sources_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
# Set debug level for our modules to see detailed timing
logging.getLogger("services.api.modules.chat").setLevel(logging.INFO)
logging.getLogger("services.api.modules.embeddings").setLevel(logging.DEBUG)
logging.getLogger("services.api.core.ai").setLevel(logging.INFO)


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
app.include_router(sources_router)
app.include_router(ingestion_router)
app.include_router(chat_router)
app.include_router(citations_router)


@app.get("/")
def root():
    """Root endpoint."""
    return {"message": "Welcome to NotebookLX API"}


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
