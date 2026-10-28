"""FastAPI main application for FinSight Intelligence."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.app.config import settings
from backend.app.db.session import init_db
from backend.app.api.routes import health, settings as settings_route, documents, chat, compare, metrics

# Logging setup
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("finsight")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database
    logger.info("Initializing FinSight Intelligence backend...")
    init_db()
    yield
    # Shutdown
    logger.info("FinSight Intelligence backend shutting down...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise Financial Document Intelligence Platform using Advanced RAG.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health.router)
app.include_router(settings_route.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(compare.router)
app.include_router(metrics.router)


# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception processing request %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "An internal server error occurred. Please consult backend logs.",
            "path": request.url.path,
        },
    )


@app.get("/")
def root():
    return {
        "app": settings.PROJECT_NAME,
        "status": "online",
        "documentation": "/docs",
        "health": "/api/health",
    }
