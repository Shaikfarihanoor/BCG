from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.routers.jobs import router as jobs_router

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup and shutdown tasks."""
    # Initialize database tables
    init_db()
    # Ensure storage directory exists
    _ = settings.storage_path
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Production-ready backend API for bulk certificate generation with "
        "background processing, per-recipient failure isolation, and ZIP packaging."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for frontend clients / testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Register API Routers
app.include_router(jobs_router)


@app.get("/", tags=["Frontend"])
def index():
    """Serve the interactive web interface dashboard."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "healthy",
        "documentation": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Health status probe endpoint."""
    return {"status": "ok", "version": settings.APP_VERSION}

