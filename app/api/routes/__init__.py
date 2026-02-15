"""API routes."""

from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.api.routes.research import router as research_router

__all__ = ["chat_router", "health_router", "research_router"]
