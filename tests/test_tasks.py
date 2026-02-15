"""Tests for asynchronous task queue and task API endpoints."""

import asyncio
import time
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from app.main import create_app
from app.models.tasks import (
    AgentType,
    ChatTaskRequest,
    ResearchTaskRequest,
    TaskStatus,
)
from app.services.tasks import TaskManager, TaskNotFoundError, TaskNotReadyError

TEST_HEADERS = {"X-API-Key": "oea_0123456789abcdef0123456789abcdef"}


async def _wait_for_status(
    manager: TaskManager,
    task_id: str,
    api_key_id: str,
    expected_status: TaskStatus,
    timeout_seconds: float = 2.0,
) -> None:
    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        current = await manager.get_task(task_id=task_id, api_key_id=api_key_id)
        if current.status == expected_status:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"Timed out waiting for {task_id} to reach {expected_status.value}")


class TestTaskManager:
    """Unit tests for TaskManager."""

    @pytest.mark.asyncio
    async def test_submit_and_complete_task(self) -> None:
        """Task should execute in background and store result."""

        async def executor(request):
            await asyncio.sleep(0.01)
            return {"agent": request.agent.value, "ok": True}

        manager = TaskManager(executor=executor, max_workers=1, task_ttl_seconds=60)
        await manager.start()
        try:
            submitted = await manager.submit_task(
                request=ChatTaskRequest(message="hello", priority=3),
                api_key_id="test-key",
            )
            await _wait_for_status(
                manager,
                submitted.task_id,
                api_key_id="test-key",
                expected_status=TaskStatus.COMPLETED,
            )

            result = await manager.get_task_result(submitted.task_id, api_key_id="test-key")
            assert result.status == TaskStatus.COMPLETED
            assert result.result == {"agent": "chat", "ok": True}
        finally:
            await manager.shutdown()

    @pytest.mark.asyncio
    async def test_get_result_not_ready(self) -> None:
        """Requesting result before completion should raise TaskNotReadyError."""

        async def executor(request):
            await asyncio.sleep(0.2)
            return {"ok": True}

        manager = TaskManager(executor=executor, max_workers=1, task_ttl_seconds=60)
        await manager.start()
        try:
            submitted = await manager.submit_task(
                request=ChatTaskRequest(message="hello"),
                api_key_id="test-key",
            )
            with pytest.raises(TaskNotReadyError):
                await manager.get_task_result(submitted.task_id, api_key_id="test-key")
        finally:
            await manager.shutdown()

    @pytest.mark.asyncio
    async def test_cancel_pending_task(self) -> None:
        """Pending tasks should be cancellable."""

        blocker = asyncio.Event()

        async def executor(request):
            await blocker.wait()
            return {"ok": True}

        manager = TaskManager(executor=executor, max_workers=1, task_ttl_seconds=60)
        await manager.start()
        try:
            first = await manager.submit_task(
                request=ChatTaskRequest(message="first", priority=10),
                api_key_id="test-key",
            )
            second = await manager.submit_task(
                request=ChatTaskRequest(message="second", priority=1),
                api_key_id="test-key",
            )

            await _wait_for_status(
                manager,
                first.task_id,
                api_key_id="test-key",
                expected_status=TaskStatus.PROCESSING,
            )

            cancelled = await manager.cancel_task(second.task_id, api_key_id="test-key")
            assert cancelled.status == TaskStatus.CANCELLED

            blocker.set()
            await _wait_for_status(
                manager,
                first.task_id,
                api_key_id="test-key",
                expected_status=TaskStatus.COMPLETED,
            )
        finally:
            await manager.shutdown()

    @pytest.mark.asyncio
    async def test_list_tasks_with_filters(self) -> None:
        """List tasks should support agent/status filters and pagination."""

        async def executor(request):
            await asyncio.sleep(0.01)
            return {"agent": request.agent.value}

        manager = TaskManager(executor=executor, max_workers=2, task_ttl_seconds=60)
        await manager.start()
        try:
            t1 = await manager.submit_task(
                request=ChatTaskRequest(message="hello"),
                api_key_id="test-key",
            )
            t2 = await manager.submit_task(
                request=ResearchTaskRequest(topic="AI safety"),
                api_key_id="test-key",
            )

            await _wait_for_status(manager, t1.task_id, "test-key", TaskStatus.COMPLETED)
            await _wait_for_status(manager, t2.task_id, "test-key", TaskStatus.COMPLETED)

            page, total = await manager.list_tasks(api_key_id="test-key", limit=1, offset=0)
            assert total == 2
            assert len(page) == 1

            research_tasks, _ = await manager.list_tasks(
                api_key_id="test-key",
                agent=AgentType.RESEARCH,
            )
            assert len(research_tasks) == 1
            assert research_tasks[0].agent == AgentType.RESEARCH

            completed_tasks, _ = await manager.list_tasks(
                api_key_id="test-key",
                status=TaskStatus.COMPLETED,
            )
            assert len(completed_tasks) == 2
        finally:
            await manager.shutdown()

    @pytest.mark.asyncio
    async def test_task_owner_isolation(self) -> None:
        """Tasks should not be visible across different API keys."""

        async def executor(request):
            return {"ok": True}

        manager = TaskManager(executor=executor, max_workers=1, task_ttl_seconds=60)
        await manager.start()
        try:
            submitted = await manager.submit_task(
                request=ChatTaskRequest(message="hello"),
                api_key_id="owner-key",
            )
            with pytest.raises(TaskNotFoundError):
                await manager.get_task(submitted.task_id, api_key_id="other-key")
        finally:
            await manager.shutdown()


class TestTaskAPI:
    """Integration tests for task endpoints."""

    @pytest.fixture
    def client(self, mocker: MockerFixture) -> TestClient:
        """Create app client with deterministic task executor."""

        async def fake_executor(request):
            await asyncio.sleep(0.01)
            if request.agent == AgentType.CHAT:
                return {"reply": f"echo:{request.message}", "agent": request.agent.value}
            return {"topic": request.topic, "agent": request.agent.value}

        mocker.patch("app.main.create_task_executor", return_value=fake_executor)
        app = create_app()
        return TestClient(app)

    @staticmethod
    def _wait_for_terminal_status(client: TestClient, task_id: str) -> dict[str, Any]:
        for _ in range(80):
            response = client.get(f"/tasks/{task_id}", headers=TEST_HEADERS)
            assert response.status_code == 200
            payload = cast(dict[str, Any], response.json())
            if payload["status"] in {"completed", "failed", "cancelled"}:
                return payload
            time.sleep(0.01)
        raise AssertionError(f"Task {task_id} did not reach terminal state")

    def test_submit_and_fetch_chat_task_result(self, client: TestClient) -> None:
        """Task endpoint should execute chat task and return result."""
        with client:
            submit = client.post(
                "/tasks",
                json={"agent": "chat", "message": "hello", "priority": 4},
                headers=TEST_HEADERS,
            )
            assert submit.status_code == 202
            task_id = submit.json()["task_id"]

            terminal = self._wait_for_terminal_status(client, task_id)
            assert terminal["status"] == "completed"

            result = client.get(f"/tasks/{task_id}/result", headers=TEST_HEADERS)
            assert result.status_code == 200
            assert result.json()["result"]["reply"] == "echo:hello"

    def test_submit_and_fetch_research_task_result(self, client: TestClient) -> None:
        """Task endpoint should execute research task and return result."""
        with client:
            submit = client.post(
                "/tasks",
                json={"agent": "research", "topic": "AI safety", "depth": "quick"},
                headers=TEST_HEADERS,
            )
            assert submit.status_code == 202
            task_id = submit.json()["task_id"]

            terminal = self._wait_for_terminal_status(client, task_id)
            assert terminal["status"] == "completed"

            result = client.get(f"/tasks/{task_id}/result", headers=TEST_HEADERS)
            assert result.status_code == 200
            assert result.json()["result"]["topic"] == "AI safety"

    def test_result_before_completion_returns_409(self, mocker: MockerFixture) -> None:
        """Result endpoint should return 409 if task is still running."""

        async def slow_executor(request):
            await asyncio.sleep(0.25)
            return {"ok": True}

        mocker.patch("app.main.create_task_executor", return_value=slow_executor)
        app = create_app()

        with TestClient(app) as client:
            submit = client.post(
                "/tasks",
                json={"agent": "chat", "message": "hello"},
                headers=TEST_HEADERS,
            )
            task_id = submit.json()["task_id"]

            result = client.get(f"/tasks/{task_id}/result", headers=TEST_HEADERS)
            assert result.status_code == 409

    def test_list_tasks_with_filter(self, client: TestClient) -> None:
        """Task listing should support filtering by agent."""
        with client:
            client.post(
                "/tasks",
                json={"agent": "chat", "message": "hello"},
                headers=TEST_HEADERS,
            )
            client.post(
                "/tasks",
                json={"agent": "research", "topic": "AI safety"},
                headers=TEST_HEADERS,
            )

            time.sleep(0.05)

            response = client.get("/tasks?agent=research", headers=TEST_HEADERS)
            assert response.status_code == 200
            data = response.json()
            assert data["total"] >= 1
            assert all(task["agent"] == "research" for task in data["tasks"])

    def test_cancel_missing_task_returns_404(self, client: TestClient) -> None:
        """Cancel should return 404 for unknown task."""
        with client:
            response = client.delete("/tasks/does-not-exist", headers=TEST_HEADERS)
            assert response.status_code == 404
