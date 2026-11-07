"""SOAR IOC Factory — FastAPI entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import health, iocs
from app.core.config import settings
from app.core.db import engine
from app.core.logging import get_logger, setup_logging

setup_logging("DEBUG" if settings.debug else "INFO")
logger = get_logger("soar.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("starting", extra={"action": "startup"})
    yield
    logger.info("shutting down", extra={"action": "shutdown"})
    engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="Intelligent Indicator Lifecycle Management — SOAR platform.",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        # Never leak internals to the client; the stack goes to structured logs.
        logger.exception("unhandled error", extra={"action": "error"})
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "path": request.url.path},
        )

    app.include_router(health.router)
    app.include_router(iocs.router, prefix=settings.api_prefix)

    return app


app = create_app()
