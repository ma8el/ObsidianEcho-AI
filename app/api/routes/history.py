"""History query and stats endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.middleware import get_authenticated_api_key
from app.models.auth import APIKey
from app.models.history import (
    ExecutionHistoryListResponse,
    HistoryStatsResponse,
    RequestHistoryListResponse,
)
from app.services.history import HistoryService

router = APIRouter(prefix="/history", tags=["history"])


def get_history_service(request: Request) -> HistoryService:
    """Fetch initialized history service from app state."""
    service = getattr(request.app.state, "history_service", None)
    if not isinstance(service, HistoryService):
        raise HTTPException(status_code=500, detail="History service is not initialized")
    return service


@router.get("/requests", response_model=RequestHistoryListResponse)
async def list_request_history(
    method: str | None = Query(default=None),
    path_contains: str | None = Query(default=None),
    status_code: int | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    api_key: APIKey = Depends(get_authenticated_api_key),
    history_service: HistoryService = Depends(get_history_service),
) -> RequestHistoryListResponse:
    """Query request history for the authenticated API key."""
    items, total = await history_service.query_requests(
        api_key_id=api_key.key_id,
        limit=limit,
        offset=offset,
        method=method,
        path_contains=path_contains,
        status_code=status_code,
        start_date=start_date,
        end_date=end_date,
    )
    return RequestHistoryListResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/executions", response_model=ExecutionHistoryListResponse)
async def list_execution_history(
    agent: str | None = Query(default=None),
    status: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    api_key: APIKey = Depends(get_authenticated_api_key),
    history_service: HistoryService = Depends(get_history_service),
) -> ExecutionHistoryListResponse:
    """Query agent execution history for the authenticated API key."""
    items, total = await history_service.query_executions(
        api_key_id=api_key.key_id,
        limit=limit,
        offset=offset,
        agent=agent,
        status=status,
        start_date=start_date,
        end_date=end_date,
    )
    return ExecutionHistoryListResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/stats", response_model=HistoryStatsResponse)
async def history_stats(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    api_key: APIKey = Depends(get_authenticated_api_key),
    history_service: HistoryService = Depends(get_history_service),
) -> HistoryStatsResponse:
    """Get aggregated request/execution statistics for the authenticated API key."""
    return await history_service.get_stats(
        api_key_id=api_key.key_id,
        start_date=start_date,
        end_date=end_date,
    )
