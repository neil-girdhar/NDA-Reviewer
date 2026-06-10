import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlmodel import Session

from database import create_db_and_tables, engine
from routers import upload, review, download
from services.storage_service import purge_stale_reviews

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
)

app = FastAPI(title="NDA Reviewer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_DIST = Path(__file__).parent.parent / "frontend" / "dist"

app.include_router(upload.router)
app.include_router(review.router)
app.include_router(download.router)


_log = logging.getLogger(__name__)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    with Session(engine) as session:
        purged = purge_stale_reviews(session)
        if purged:
            _log.info("Purged %d stale unsaved review(s) on startup.", purged)


@app.get("/")
def serve_index():
    return FileResponse(_DIST / "index.html")

if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")


@app.get("/health")
def health():
    return {"status": "ok"}
