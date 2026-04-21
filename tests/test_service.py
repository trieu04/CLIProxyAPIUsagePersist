import unittest
from typing import cast

from src.cliproxyapi_usage_persist.service import ManagementClientLike, SnapshotStoreLike, UsagePersistService


def _snapshot(timestamp: str) -> dict[str, object]:
    return {
        "apis": {
            "key": {
                "models": {
                    "gpt-5.4": {
                        "details": [
                            {
                                "timestamp": timestamp,
                                "latency_ms": 0,
                                "source": "user@example.com",
                                "auth_index": "0",
                                "tokens": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                                "failed": False,
                            }
                        ]
                    }
                }
            }
        }
    }


class FakeClient:
    def __init__(self, exported: dict[str, object]) -> None:
        self.exported = exported
        self.imported: list[dict[str, object]] = []

    def export_usage_snapshot(self) -> dict[str, object]:
        return {"version": 1, "usage": self.exported}

    def import_usage_snapshot(self, snapshot: dict[str, object]) -> dict[str, object]:
        self.imported.append(snapshot)
        return {"added": 1, "skipped": 0}


class FakeStore:
    def __init__(self, initial: dict[str, object]) -> None:
        self.current = initial
        self.saved: list[dict[str, object]] = []

    def load(self) -> dict[str, object]:
        return self.current

    def save(self, snapshot: dict[str, object]) -> None:
        self.current = snapshot
        self.saved.append(snapshot)


class ServiceTests(unittest.TestCase):
    def test_startup_reconcile_imports_only_when_merged_snapshot_is_fuller(self) -> None:
        client = FakeClient(exported=_snapshot("2026-03-20T12:00:00Z"))
        store = FakeStore(initial=_snapshot("2026-03-21T12:00:00Z"))
        service = UsagePersistService(
            client=cast(ManagementClientLike, client),
            store=cast(SnapshotStoreLike, store),
            interval_seconds=3600,
            retry_attempts=2,
            retry_base_delay_seconds=1.0,
            retry_max_delay_seconds=2.0,
            sleep=lambda _: None,
        )
        result = service.reconcile_once()
        self.assertTrue(result.import_performed)
        self.assertEqual(result.exported_unique_requests, 1)
        self.assertEqual(result.merged_unique_requests, 2)
        self.assertEqual(len(client.imported), 1)
        self.assertEqual(store.saved[-1]["total_requests"], 2)

    def test_periodic_cycle_skips_import_when_remote_already_full(self) -> None:
        snapshot = _snapshot("2026-03-20T12:00:00Z")
        client = FakeClient(exported=snapshot)
        store = FakeStore(initial=snapshot)
        service = UsagePersistService(
            client=cast(ManagementClientLike, client),
            store=cast(SnapshotStoreLike, store),
            interval_seconds=3600,
            retry_attempts=2,
            retry_base_delay_seconds=1.0,
            retry_max_delay_seconds=2.0,
            sleep=lambda _: None,
        )
        result = service.reconcile_once()
        self.assertFalse(result.import_performed)
        self.assertEqual(client.imported, [])
        self.assertEqual(store.saved[-1]["total_requests"], 1)

    def test_reconcile_imports_when_remote_has_dedup_collisions_but_store_has_extra_unique_detail(self) -> None:
        exported = cast(
            dict[str, object],
            {
            "apis": {
                "key": {
                    "models": {
                        "gpt-5.4": {
                            "details": [
                                {
                                    "timestamp": "2026-03-20T12:00:00Z",
                                    "latency_ms": 0,
                                    "source": "user@example.com",
                                    "auth_index": "0",
                                    "tokens": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                                    "failed": False,
                                },
                                {
                                    "timestamp": "2026-03-20T12:00:00Z",
                                    "latency_ms": 2500,
                                    "source": "user@example.com",
                                    "auth_index": "0",
                                    "tokens": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                                    "failed": False,
                                },
                            ]
                        }
                    }
                }
            }
            },
        )
        store_snapshot = _snapshot("2026-03-21T12:00:00Z")
        client = FakeClient(exported=exported)
        store = FakeStore(initial=store_snapshot)
        service = UsagePersistService(
            client=cast(ManagementClientLike, client),
            store=cast(SnapshotStoreLike, store),
            interval_seconds=3600,
            retry_attempts=2,
            retry_base_delay_seconds=1.0,
            retry_max_delay_seconds=2.0,
            sleep=lambda _: None,
        )
        result = service.reconcile_once()
        self.assertTrue(result.import_performed)
        self.assertEqual(result.exported_unique_requests, 1)
        self.assertEqual(result.merged_unique_requests, 2)
        self.assertEqual(len(client.imported), 1)


if __name__ == "__main__":
    unittest.main()
