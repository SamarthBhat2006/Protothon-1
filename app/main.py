"""
AI Meeting-to-Action System — FastAPI Application Entry Point
"""
import logging
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import meetings, board

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Captures meeting discussions and converts them into structured action items for engineering teams.",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    logger.info("=" * 60)
    logger.info(f"  {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info("=" * 60)

    # Create dirs
    os.makedirs("data", exist_ok=True)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.DELTA_PATH, exist_ok=True)

    # Init database
    init_db()
    logger.info("Database initialized")

    # Status checks
    logger.info(f"Sarvam AI key: {'✓ configured' if settings.SARVAM_API_KEY else '✗ not set (mock mode)'}")
    logger.info(f"Google API key: {'✓ configured' if settings.GOOGLE_API_KEY else '✗ not set (mock mode)'}")
    logger.info("Server ready at http://localhost:8000")
    logger.info("=" * 60)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(meetings.router)
app.include_router(board.router)

# ── Static files ──────────────────────────────────────────────────────────────
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    """Serve the frontend SPA."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "message": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "sarvam_configured": bool(settings.SARVAM_API_KEY),
        "google_configured": bool(settings.GOOGLE_API_KEY),
    }