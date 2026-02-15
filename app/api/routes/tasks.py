"""Task management API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.agents.chat import ChatAgent
from app.agents.research import ResearchAgent
from app.api.middleware import get_authenticated_api_key
from app.core.config import Settings
from app.core.logging import get_logger
from app.models.auth import APIKey
from app.models.tasks import (
    AgentType,
    ChatTaskRequest,
    ResearchTaskRequest,
    TaskListResponse,
    TaskRequest,
    TaskResultResponse,
    TaskStatus,
    TaskStatusResponse,
    TaskSubmissionResponse,
)
from app.services.providers import ProviderManager
from app.services.tasks import (
    TaskCancellationError,
    TaskExecutor,
    TaskManager,
    TaskNotFoundError,
    TaskNotReadyError,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/tasks", tags=["tasks"])


def create_task_executor(settings: Settings) -> TaskExecutor:
    """Create task executor callable for background workers."""
    provider_manager = ProviderManager(settings.providers)
    chat_agent = ChatAgent(provider_manager)
    research_agent = ResearchAgent(provider_manager)

    async def execute(task_request: TaskRequest) -> dict[str, Any]:
        if isinstance(task_request, ChatTaskRequest):
            chat_result = await chat_agent.chat(
                message=task_request.message,
                provider=task_request.provider,
            )
            return chat_result.model_dump(mode="json")

        if isinstance(task_request, ResearchTaskRequest):
            research_result = await research_agent.research(
                topic=task_request.topic,
                depth=task_request.depth,
                provider=task_request.provider,
                focus_areas=task_request.focus_areas,
            )
            return research_result.model_dump(mode="json")

        raise ValueError(f"Unsupported task request type: {type(task_request)!r}")

    return execute


def get_task_manager(request: Request) -> TaskManager:
    """Fetch the initialized task manager from app state."""
    manager = getattr(request.app.state, "task_manager", None)
    if not isinstance(manager, TaskManager):
        raise HTTPException(status_code=500, detail="Task manager is not initialized")
    return manager


@router.post("", response_model=TaskSubmissionResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_task(
    request: TaskRequest,
    api_key: APIKey = Depends(get_authenticated_api_key),
    task_manager: TaskManager = Depends(get_task_manager),
) -> TaskSubmissionResponse:
    """Submit a task for asynchronous processing."""
    task = await task_manager.submit_task(request=request, api_key_id=api_key.key_id)
    return TaskSubmissionResponse(
        task_id=task.task_id,
        status=task.status,
        status_url=f"/tasks/{task.task_id}",
    )


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    api_key: APIKey = Depends(get_authenticated_api_key),
    task_manager: TaskManager = Depends(get_task_manager),
) -> TaskStatusResponse:
    """Get task status."""
    try:
        return await task_manager.get_task(task_id=task_id, api_key_id=api_key.key_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc


@router.get("/{task_id}/result", response_model=TaskResultResponse)
async def get_task_result(
    task_id: str,
    api_key: APIKey = Depends(get_authenticated_api_key),
    task_manager: TaskManager = Depends(get_task_manager),
) -> TaskResultResponse:
    """Get completed task result."""
    try:
        return await task_manager.get_task_result(task_id=task_id, api_key_id=api_key.key_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    except TaskNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/{task_id}", response_model=TaskStatusResponse)
async def cancel_task(
    task_id: str,
    api_key: APIKey = Depends(get_authenticated_api_key),
    task_manager: TaskManager = Depends(get_task_manager),
) -> TaskStatusResponse:
    """Cancel a task if still pending/processing."""
    try:
        return await task_manager.cancel_task(task_id=task_id, api_key_id=api_key.key_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    except TaskCancellationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    agent: AgentType | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    api_key: APIKey = Depends(get_authenticated_api_key),
    task_manager: TaskManager = Depends(get_task_manager),
) -> TaskListResponse:
    """List tasks owned by API key with filtering and pagination."""
    tasks, total = await task_manager.list_tasks(
        api_key_id=api_key.key_id,
        status=status_filter,
        agent=agent,
        limit=limit,
        offset=offset,
    )
    return TaskListResponse(total=total, limit=limit, offset=offset, tasks=tasks)
