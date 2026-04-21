"""Startup reconcile and periodic sync loop."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Protocol

from .retry import retry_call
from .usage_merge import deduped_unique_request_count, merge_snapshots, rebuild_snapshot


class ManagementClientLike(Protocol):
    def export_usage_snapshot(self) -> dict[str, object]: ...

    def import_usage_snapshot(self, snapshot: dict[str, object]) -> dict[str, object]: ...


class SnapshotStoreLike(Protocol):
    def load(self) -> dict[str, object]: ...

    def save(self, snapshot: dict[str, object]) -> None: ...


@dataclass(frozen=True)
class CycleResult:
    exported_unique_requests: int
    merged_unique_requests: int
    import_performed: bool
    added: int
    skipped: int


class UsagePersistService:
    def __init__(
        self,
        *,
        client: ManagementClientLike,
        store: SnapshotStoreLike,
        interval_seconds: int,
        retry_attempts: int,
        retry_base_delay_seconds: float,
        retry_max_delay_seconds: float,
        sleep: Callable[[float], None] = time.sleep,
        logger: logging.Logger | None = None,
    ) -> None:
        self.client = client
        self.store = store
        self.interval_seconds = interval_seconds
        self.retry_attempts = retry_attempts
        self.retry_base_delay_seconds = retry_base_delay_seconds
        self.retry_max_delay_seconds = retry_max_delay_seconds
        self.sleep = sleep
        self.logger = logger or logging.getLogger(__name__)

    def run(self) -> None:
        self._run_cycle("startup")
        while True:
            self.sleep(self.interval_seconds)
            self._run_cycle("periodic")

    def reconcile_once(self) -> CycleResult:
        exported_payload = self._with_retry(self.client.export_usage_snapshot)
        exported_usage = exported_payload.get("usage")
        if not isinstance(exported_usage, dict):
            raise TypeError("export response missing usage object")
        exported_snapshot = rebuild_snapshot(exported_usage)
        persisted_snapshot = self.store.load()
        merged_snapshot, merge_result = merge_snapshots(exported_snapshot, persisted_snapshot)
        exported_unique = deduped_unique_request_count(exported_snapshot)
        merged_unique = deduped_unique_request_count(merged_snapshot)
        self.store.save(merged_snapshot)

        import_performed = merged_unique > exported_unique
        if import_performed:
            self._with_retry(lambda: self.client.import_usage_snapshot(merged_snapshot))
        return CycleResult(
            exported_unique_requests=exported_unique,
            merged_unique_requests=merged_unique,
            import_performed=import_performed,
            added=merge_result["added"],
            skipped=merge_result["skipped"],
        )

    def _with_retry(self, operation):
        return retry_call(
            operation,
            attempts=self.retry_attempts,
            base_delay_seconds=self.retry_base_delay_seconds,
            max_delay_seconds=self.retry_max_delay_seconds,
            sleep=self.sleep,
        )

    def _run_cycle(self, label: str) -> None:
        try:
            result = self.reconcile_once()
            self.logger.info(
                "%s sync finished: exported=%s merged=%s imported=%s added=%s skipped=%s",
                label,
                result.exported_unique_requests,
                result.merged_unique_requests,
                result.import_performed,
                result.added,
                result.skipped,
            )
        except Exception:
            self.logger.exception("%s sync failed", label)
