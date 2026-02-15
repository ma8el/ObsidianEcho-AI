"""Asynchronous in-memory task queue service."""

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import count
from typing import Any
from uuid import uuid4

from app.core.logging import get_logger
from app.models.tasks import (
    AgentType,
    ChatTaskRequest,
    ResearchTaskRequest,
    TaskRequest,
    TaskResultResponse,
    TaskStatus,
    TaskStatusResponse,
)

logger = get_logger(__name__)

TaskExecutor = Callable[[TaskRequest], Coroutine[Any, Any, dict[str, Any]]]
TERMINAL_STATUSES = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}


class TaskError(Exception):
    """Base exception for task operations."""


class TaskNotFoundError(TaskError):
    """Raised when task is not found or not visible to caller."""


class TaskNotReadyError(TaskError):
    """Raised when task result is requested before completion."""


class TaskCancellationError(TaskError):
    """Raised when task cancellation is not possible."""


@dataclass
class StoredTask:
    """Internal task state."""

    task_id: str
    api_key_id: str
    request: ChatTaskRequest | ResearchTaskRequest
    agent: AgentType
    priority: int
    status: TaskStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None
    error: str | None = None
    result: dict[str, Any] | None = None
    cancel_requested: bool = False


class TaskManager:
    """In-memory async task queue with worker pool and TTL cleanup."""

    def __init__(
        self,
        executor: TaskExecutor,
        *,
        max_workers: int = 2,
        task_ttl_seconds: int = 3600,
        cleanup_interval_seconds: int = 30,
    ) -> None:
        self._executor = executor
        self._max_workers = max_workers
        self._task_ttl_seconds = task_ttl_seconds
        self._cleanup_interval_seconds = cleanup_interval_seconds

        self._tasks: dict[str, StoredTask] = {}
        self._queue: asyncio.PriorityQueue[tuple[int, int, str]] = asyncio.PriorityQueue()
        self._active_executions: dict[str, asyncio.Task[dict[str, Any]]] = {}

        self._sequence = count()
        self._lock = asyncio.Lock()
        self._workers: list[asyncio.Task[None]] = []
        self._cleanup_task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        """Start queue workers and cleanup loop."""
        if self._running:
            return

        self._running = True
        self._workers = [
            asyncio.create_task(self._worker_loop(worker_id), name=f"task-worker-{worker_id}")
            for worker_id in range(self._max_workers)
        ]
        self._cleanup_task = asyncio.create_task(self._cleanup_loop(), name="task-cleanup")

        logger.info("Task manager started", extra={"workers": self._max_workers})

    async def shutdown(self) -> None:
        """Stop workers and cleanup loop."""
        if not self._running:
            return

        self._running = False

        for execution in list(self._active_executions.values()):
            execution.cancel()

        for worker in self._workers:
            worker.cancel()

        if self._cleanup_task is not None:
            self._cleanup_task.cancel()

        await asyncio.gather(*self._workers, return_exceptions=True)
        if self._cleanup_task is not None:
            await asyncio.gather(self._cleanup_task, return_exceptions=True)

        self._workers = []
        self._cleanup_task = None

        logger.info("Task manager stopped")

    async def submit_task(self, request: TaskRequest, api_key_id: str) -> TaskStatusResponse:
        """Submit a task for asynchronous execution."""
        task_id = str(uuid4())
        now = datetime.now(UTC)

        task = StoredTask(
            task_id=task_id,
            api_key_id=api_key_id,
            request=request,
            agent=request.agent,
            priority=request.priority,
            status=TaskStatus.PENDING,
            created_at=now,
        )

        async with self._lock:
            self._tasks[task_id] = task
            await self._queue.put((-request.priority, next(self._sequence), task_id))

        logger.info(
            "Task submitted",
            extra={
                "task_id": task_id,
                "agent": request.agent.value,
                "priority": request.priority,
                "api_key_id": api_key_id,
            },
        )

        return self._to_status_response(task)

    async def get_task(self, task_id: str, api_key_id: str) -> TaskStatusResponse:
        """Get task status for owner."""
        task = await self._get_task_for_owner(task_id, api_key_id)
        return self._to_status_response(task)

    async def get_task_result(self, task_id: str, api_key_id: str) -> TaskResultResponse:
        """Get completed task result for owner."""
        task = await self._get_task_for_owner(task_id, api_key_id)

        if task.status != TaskStatus.COMPLETED:
            raise TaskNotReadyError(f"Task {task_id} is not completed")

        return self._to_result_response(task)

    async def cancel_task(self, task_id: str, api_key_id: str) -> TaskStatusResponse:
        """Cancel a pending or processing task."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.api_key_id != api_key_id:
                raise TaskNotFoundError(f"Task {task_id} not found")

            if task.status in TERMINAL_STATUSES:
                raise TaskCancellationError(f"Task {task_id} is already {task.status.value}")

            task.cancel_requested = True
            self._mark_cancelled(task)

            active_execution = self._active_executions.get(task_id)
            if active_execution is not None:
                active_execution.cancel()

        logger.info("Task cancelled", extra={"task_id": task_id, "api_key_id": api_key_id})
        return self._to_status_response(task)

    async def list_tasks(
        self,
        *,
        api_key_id: str,
        status: TaskStatus | None = None,
        agent: AgentType | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[TaskStatusResponse], int]:
        """List tasks for owner with filtering and pagination."""
        async with self._lock:
            tasks = [task for task in self._tasks.values() if task.api_key_id == api_key_id]

        if status is not None:
            tasks = [task for task in tasks if task.status == status]
        if agent is not None:
            tasks = [task for task in tasks if task.agent == agent]

        tasks.sort(key=lambda task: task.created_at, reverse=True)
        total = len(tasks)
        page = tasks[offset : offset + limit]

        return [self._to_status_response(task) for task in page], total

    async def _worker_loop(self, worker_id: int) -> None:
        """Worker loop that processes tasks from queue."""
        while self._running:
            try:
                _, _, task_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            try:
                await self._process_task(task_id, worker_id)
            finally:
                self._queue.task_done()

    async def _process_task(self, task_id: str, worker_id: int) -> None:
        """Process a single queued task."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return

            if task.status != TaskStatus.PENDING:
                return

            if task.cancel_requested:
                self._mark_cancelled(task)
                return

            task.status = TaskStatus.PROCESSING
            task.started_at = datetime.now(UTC)

        logger.info("Task processing started", extra={"task_id": task_id, "worker": worker_id})

        execution = asyncio.create_task(self._executor(task.request))
        async with self._lock:
            self._active_executions[task_id] = execution

        try:
            result = await execution
        except asyncio.CancelledError:
            async with self._lock:
                current = self._tasks.get(task_id)
                if current is not None and current.status not in TERMINAL_STATUSES:
                    self._mark_cancelled(current)
            return
        except Exception as exc:  # noqa: BLE001
            async with self._lock:
                current = self._tasks.get(task_id)
                if current is not None and current.status not in TERMINAL_STATUSES:
                    self._mark_failed(current, str(exc))

            logger.error(
                "Task processing failed",
                extra={"task_id": task_id, "worker": worker_id, "error": str(exc)},
                exc_info=True,
            )
            return
        finally:
            async with self._lock:
                self._active_executions.pop(task_id, None)

        async with self._lock:
            current = self._tasks.get(task_id)
            if current is None:
                return

            if current.status == TaskStatus.CANCELLED or current.cancel_requested:
                self._mark_cancelled(current)
                return

            self._mark_completed(current, result)

        logger.info(
            "Task processing completed",
            extra={"task_id": task_id, "worker": worker_id},
        )

    async def _cleanup_loop(self) -> None:
        """Periodic cleanup of expired finished tasks."""
        while self._running:
            try:
                await asyncio.sleep(self._cleanup_interval_seconds)
            except asyncio.CancelledError:
                break

            now = datetime.now(UTC)
            async with self._lock:
                expired_task_ids = [
                    task_id
                    for task_id, task in self._tasks.items()
                    if task.status in TERMINAL_STATUSES
                    and task.expires_at is not None
                    and task.expires_at <= now
                ]

                for task_id in expired_task_ids:
                    self._tasks.pop(task_id, None)

            if expired_task_ids:
                logger.info("Expired tasks cleaned", extra={"count": len(expired_task_ids)})

    async def _get_task_for_owner(self, task_id: str, api_key_id: str) -> StoredTask:
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.api_key_id != api_key_id:
                raise TaskNotFoundError(f"Task {task_id} not found")
            return task

    def _mark_completed(self, task: StoredTask, result: dict[str, Any]) -> None:
        now = datetime.now(UTC)
        task.status = TaskStatus.COMPLETED
        task.result = result
        task.error = None
        task.completed_at = now
        task.expires_at = now + timedelta(seconds=self._task_ttl_seconds)

    def _mark_failed(self, task: StoredTask, error: str) -> None:
        now = datetime.now(UTC)
        task.status = TaskStatus.FAILED
        task.result = None
        task.error = error
        task.completed_at = now
        task.expires_at = now + timedelta(seconds=self._task_ttl_seconds)

    def _mark_cancelled(self, task: StoredTask) -> None:
        now = datetime.now(UTC)
        task.status = TaskStatus.CANCELLED
        task.result = None
        task.error = None
        task.completed_at = now
        task.expires_at = now + timedelta(seconds=self._task_ttl_seconds)

    @staticmethod
    def _to_status_response(task: StoredTask) -> TaskStatusResponse:
        return TaskStatusResponse(
            task_id=task.task_id,
            agent=task.agent,
            status=task.status,
            priority=task.priority,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            expires_at=task.expires_at,
            error=task.error,
        )

    @staticmethod
    def _to_result_response(task: StoredTask) -> TaskResultResponse:
        return TaskResultResponse(
            task_id=task.task_id,
            agent=task.agent,
            status=task.status,
            priority=task.priority,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            expires_at=task.expires_at,
            error=task.error,
            result=task.result,
        )
