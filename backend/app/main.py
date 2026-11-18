"""SOAR IOC Factory — FastAPI entrypoint."""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, dashboard, health, iocs, operations, soc
from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.core.logging import get_logger, setup_logging
from app.core.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from app.core.security import require_viewer

setup_logging("DEBUG" if settings.debug else "INFO")
logger = get_logger("soar.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    problems = settings.production_errors()
    if problems:
        # Fail closed: a misconfigured production API must not start.
        raise RuntimeError("configuration de production invalide : " + " ; ".join(problems))
    if not settings.auth_enabled:
        logger.warning("AUTH_ENABLED=false — API ouverte (dev uniquement)", extra={"action": "startup"})
    try:
        with SessionLocal() as db:
            created = auth.bootstrap_admin(db)
            if created:
                logger.info("bootstrap admin created", extra={"action": "bootstrap", "user": created})
    except RuntimeError:
        raise
    except Exception:  # DB not migrated yet: the API still starts, /ready reports it
        logger.exception("admin bootstrap skipped", extra={"action": "bootstrap"})
    logger.info("starting", extra={"action": "startup"})
    yield
    logger.info("shutting down", extra={"action": "shutdown"})
    engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="Intelligent Indicator Lifecycle Management — SOAR platform.",
        version="1.0.0",
        lifespan=lifespan,
        # Interactive docs are a development aid, not a production surface.
        docs_url=None if settings.app_env == "production" else "/docs",
        redoc_url=None if settings.app_env == "production" else "/redoc",
        openapi_url=None if settings.app_env == "production" else "/openapi.json",
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, per_minute=settings.rate_limit_per_minute,
                       login_per_minute=settings.login_rate_limit_per_minute)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=False,  # Bearer tokens, no cookies
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-API-Key", "X-Actor"],
    )

    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        # Never leak internals to the client; the stack goes to structured logs.
        logger.exception("unhandled error", extra={"action": "error"})
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "path": request.url.path},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Field-level messages only: never echo the submitted values (passwords).
        errors = [{"loc": list(e.get("loc", [])), "msg": e.get("msg")} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": "Requête invalide", "errors": errors})

    viewer = [Depends(require_viewer)]
    app.include_router(health.router)
    app.include_router(auth.router, prefix=settings.api_prefix)
    app.include_router(auth.users_router, prefix=settings.api_prefix)
    # Reads need an authenticated viewer; writes add require_analyst per route.
    app.include_router(iocs.router, prefix=settings.api_prefix, dependencies=viewer)
    app.include_router(operations.router, prefix=settings.api_prefix, dependencies=viewer)
    app.include_router(dashboard.router, prefix=settings.api_prefix, dependencies=viewer)
    app.include_router(soc.router, prefix=settings.api_prefix, dependencies=viewer)

    return app


app = create_app()
