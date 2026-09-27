"""FastAPI application entry point: `uvicorn app.main:app`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.observability import init_sentry
from app.core.redis import get_redis
from app.db.session import get_engine
from app.services.ai.embeddings import check_embedding_config
from app.services.ai.llm.factory import check_llm_config, llm_http_client

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    check_embedding_config(settings)  # a wrong EMBEDDING_DIM fails here, not on first save
    check_llm_config(settings)
    from app.workers.broker import broker  # the API only enqueues; the worker consumes

    await broker.startup()
    log.info("api.startup", app_env=settings.app_env, cors_origins=settings.cors_origin_list)
    yield
    await broker.shutdown()
    await llm_http_client().aclose()
    # Close pooled connections cleanly so shutdown doesn't leave sockets open.
    await get_engine().dispose()
    await get_redis().aclose()
    log.info("api.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.app_env, settings.log_level)
    init_sentry(settings, component="api")
    app = FastAPI(
        title="DevFlow API",
        version="0.1.0",
        lifespan=lifespan,
        # Interactive docs only outside production; /openapi.json stays for type generation.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
    )
    register_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )
    # Added last, so it is outermost: every response, even a CORS rejection, gets an id.
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health.router)
    app.include_router(api_router)
    return app


app = create_app()
