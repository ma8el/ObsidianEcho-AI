"""JSONL-based request and execution history service."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from app.core.logging import get_logger
from app.models.history import ExecutionHistoryEntry, HistoryStatsResponse, RequestHistoryEntry

logger = get_logger(__name__)
ModelT = TypeVar("ModelT", bound=BaseModel)


class HistoryService:
    """File-backed history storage with query and stats helpers."""

    def __init__(self, *, enabled: bool, storage_dir: str, retention_days: int = 30) -> None:
        self.enabled = enabled
        self.storage_dir = Path(storage_dir)
        self.retention_days = retention_days

        if self.enabled:
            self.storage_dir.mkdir(parents=True, exist_ok=True)

    async def cleanup_old_files(self) -> None:
        """Delete history files older than retention window."""
        if not self.enabled:
            return

        cutoff = datetime.now(UTC).date() - timedelta(days=self.retention_days)
        for history_file in self.storage_dir.glob("*.jsonl"):
            file_date = self._extract_date_from_file_name(history_file)
            if file_date is not None and file_date < cutoff:
                history_file.unlink(missing_ok=True)

    async def record_request(
        self,
        *,
        request_id: str | None,
        api_key_id: str | None,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        client: str | None,
        error: str | None = None,
    ) -> None:
        """Append a request history record."""
        if not self.enabled:
            return

        entry = RequestHistoryEntry(
            timestamp=datetime.now(UTC),
            request_id=request_id,
            api_key_id=api_key_id,
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=round(duration_ms, 2),
            client=client,
            error=error,
        )
        self._append_jsonl("requests", entry.model_dump(mode="json"))

    async def record_execution(
        self,
        *,
        request_id: str | None,
        api_key_id: str | None,
        agent: str,
        status: str,
        provider: str | None,
        model: str | None,
        duration_seconds: float | None,
        tokens_used: int | None,
        estimated_cost: float | None,
        error: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        """Append an agent execution history record."""
        if not self.enabled:
            return

        entry = ExecutionHistoryEntry(
            timestamp=datetime.now(UTC),
            request_id=request_id,
            api_key_id=api_key_id,
            agent=agent,
            status=status,
            provider=provider,
            model=model,
            duration_seconds=duration_seconds,
            tokens_used=tokens_used,
            estimated_cost=estimated_cost,
            error=error,
            metadata=dict(metadata) if metadata is not None else {},
        )
        self._append_jsonl("executions", entry.model_dump(mode="json"))

    async def query_requests(
        self,
        *,
        api_key_id: str,
        limit: int,
        offset: int,
        method: str | None = None,
        path_contains: str | None = None,
        status_code: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[list[RequestHistoryEntry], int]:
        """Query request history with filtering and pagination."""
        entries = self._read_entries(
            prefix="requests",
            model_cls=RequestHistoryEntry,
            start_date=start_date,
            end_date=end_date,
        )

        filtered = [entry for entry in entries if entry.api_key_id == api_key_id]
        if method is not None:
            filtered = [entry for entry in filtered if entry.method.lower() == method.lower()]
        if path_contains is not None:
            filtered = [entry for entry in filtered if path_contains in entry.path]
        if status_code is not None:
            filtered = [entry for entry in filtered if entry.status_code == status_code]

        filtered.sort(key=lambda entry: entry.timestamp, reverse=True)
        total = len(filtered)
        return filtered[offset : offset + limit], total

    async def query_executions(
        self,
        *,
        api_key_id: str,
        limit: int,
        offset: int,
        agent: str | None = None,
        status: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[list[ExecutionHistoryEntry], int]:
        """Query execution history with filtering and pagination."""
        entries = self._read_entries(
            prefix="executions",
            model_cls=ExecutionHistoryEntry,
            start_date=start_date,
            end_date=end_date,
        )

        filtered = [entry for entry in entries if entry.api_key_id == api_key_id]
        if agent is not None:
            filtered = [entry for entry in filtered if entry.agent == agent]
        if status is not None:
            filtered = [entry for entry in filtered if entry.status == status]

        filtered.sort(key=lambda entry: entry.timestamp, reverse=True)
        total = len(filtered)
        return filtered[offset : offset + limit], total

    async def get_stats(
        self,
        *,
        api_key_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> HistoryStatsResponse:
        """Aggregate request and execution metrics."""
        requests = self._read_entries(
            prefix="requests",
            model_cls=RequestHistoryEntry,
            start_date=start_date,
            end_date=end_date,
        )
        requests = [entry for entry in requests if entry.api_key_id == api_key_id]

        executions = self._read_entries(
            prefix="executions",
            model_cls=ExecutionHistoryEntry,
            start_date=start_date,
            end_date=end_date,
        )
        executions = [entry for entry in executions if entry.api_key_id == api_key_id]

        request_count = len(requests)
        request_error_count = len([entry for entry in requests if entry.status_code >= 400])
        avg_duration = (
            sum(entry.duration_ms for entry in requests) / request_count
            if request_count > 0
            else 0.0
        )

        execution_count = len(executions)
        execution_success_count = len(
            [entry for entry in executions if entry.status == "completed"]
        )
        execution_failure_count = len([entry for entry in executions if entry.status == "failed"])

        total_tokens_used = sum(entry.tokens_used or 0 for entry in executions)
        total_estimated_cost = round(sum(entry.estimated_cost or 0.0 for entry in executions), 6)

        return HistoryStatsResponse(
            api_key_id=api_key_id,
            start_date=start_date,
            end_date=end_date,
            request_count=request_count,
            request_error_count=request_error_count,
            average_request_duration_ms=round(avg_duration, 2),
            execution_count=execution_count,
            execution_success_count=execution_success_count,
            execution_failure_count=execution_failure_count,
            total_tokens_used=total_tokens_used,
            total_estimated_cost=total_estimated_cost,
        )

    def _append_jsonl(self, prefix: str, payload: dict[str, object]) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.storage_dir / f"{prefix}-{datetime.now(UTC).date().isoformat()}.jsonl"
        with file_path.open("a", encoding="utf-8") as history_file:
            history_file.write(json.dumps(payload, ensure_ascii=True))
            history_file.write("\n")

    def _read_entries(
        self,
        *,
        prefix: str,
        model_cls: type[ModelT],
        start_date: date | None,
        end_date: date | None,
    ) -> list[ModelT]:
        if not self.enabled:
            return []

        entries = []
        for file_path in self._list_files(prefix=prefix, start_date=start_date, end_date=end_date):
            with file_path.open(encoding="utf-8") as history_file:
                for line in history_file:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        raw = json.loads(line)
                        entries.append(model_cls.model_validate(raw))
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "Skipping malformed history record",
                            extra={"file": str(file_path), "error": str(exc)},
                        )
        return entries

    def _list_files(
        self,
        *,
        prefix: str,
        start_date: date | None,
        end_date: date | None,
    ) -> list[Path]:
        all_files = sorted(self.storage_dir.glob(f"{prefix}-*.jsonl"))
        selected_files: list[Path] = []

        for file_path in all_files:
            file_date = self._extract_date_from_file_name(file_path)
            if file_date is None:
                continue
            if start_date is not None and file_date < start_date:
                continue
            if end_date is not None and file_date > end_date:
                continue
            selected_files.append(file_path)

        return selected_files

    @staticmethod
    def _extract_date_from_file_name(file_path: Path) -> date | None:
        try:
            suffix = file_path.stem.split("-", maxsplit=1)[1]
            return date.fromisoformat(suffix)
        except Exception:  # noqa: BLE001
            return None
