"""API routes."""

from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.api.routes.history import router as history_router
from app.api.routes.research import router as research_router
from app.api.routes.tasks import router as tasks_router

__all__ = ["chat_router", "health_router", "history_router", "research_router", "tasks_router"]
