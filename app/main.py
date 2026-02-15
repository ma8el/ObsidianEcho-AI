"""Main FastAPI application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware import RequestIDMiddleware
from app.api.routes import chat_router, health_router, history_router, research_router, tasks_router
from app.api.routes.tasks import create_task_executor
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.services.history import HistoryService
from app.services.tasks import TaskManager

settings = get_settings()
setup_logging(settings)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info(
        "Starting ObsidianEcho-AI service",
        extra={"version": settings.version, "debug": settings.debug},
    )

    history_service = HistoryService(
        enabled=settings.history.enabled,
        storage_dir=settings.history.storage_dir,
        retention_days=settings.history.retention_days,
    )
    await history_service.cleanup_old_files()
    app.state.history_service = history_service

    task_manager = TaskManager(
        executor=create_task_executor(settings),
        max_workers=2,
        task_ttl_seconds=3600,
        cleanup_interval_seconds=30,
    )
    await task_manager.start()
    app.state.task_manager = task_manager

    yield
    # Shutdown
    await app.state.task_manager.shutdown()
    logger.info("Shutting down ObsidianEcho-AI service")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        FastAPI: Configured FastAPI application instance
    """
    app = FastAPI(
        title=settings.app_name,
        description="AI-powered agents for generating Obsidian markdown notes",
        version=settings.version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
        debug=settings.debug,
    )

    # Add Request ID middleware (should be first to track all requests)
    app.add_middleware(RequestIDMiddleware)

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(history_router)
    app.include_router(chat_router)
    app.include_router(research_router)
    app.include_router(tasks_router)

    logger.info("FastAPI application created successfully")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
