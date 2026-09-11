from pathlib import Path

from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.database import init_db, get_db
from app.api.routes.documents import router as documents_router
from app.utils.exceptions import AppError
from app.repositories import document_repository

setup_logging()
logger = get_logger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(
    title=settings.APP_NAME,
    description="Intelligent document extraction, validation & API platform.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)

templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")


@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("Application startup complete.")


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    logger.warning("AppError: %s - %s", exc.code, exc.message)
    return JSONResponse(status_code=exc.status_code,
                         content={"error": {"code": exc.code, "message": exc.message}})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception")
    return JSONResponse(status_code=500,
                         content={"error": {"code": "INTERNAL_ERROR",
                                             "message": "An unexpected error occurred."}})


# --------------------------------------------------------------------- #
# Frontend view routes (server-rendered HTML, calls the JSON API via JS)
# --------------------------------------------------------------------- #
@app.get("/")
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/documents/{document_name}/view")
def document_view(request: Request, document_name: str):
    return templates.TemplateResponse(
        "document_result.html", {"request": request, "document_name": document_name}
    )
