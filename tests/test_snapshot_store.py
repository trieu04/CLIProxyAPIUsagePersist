import json
import tempfile
import unittest

from src.cliproxyapi_usage_persist.snapshot_store import SnapshotStore


class SnapshotStoreTests(unittest.TestCase):
    def test_snapshot_store_loads_empty_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SnapshotStore(f"{directory}/usage.json")
            self.assertEqual(store.load()["apis"], {})

    def test_snapshot_store_writes_atomically_and_normalizes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = f"{directory}/usage.json"
            store = SnapshotStore(path)
            store.save({"apis": {"key": {"models": {"gpt-5.4": {"details": [{"timestamp": "2026-03-20T12:00:00Z", "tokens": {"input_tokens": 1, "output_tokens": 2}, "source": "", "auth_index": "", "failed": False}]}}}}})
            with open(path, encoding="utf-8") as handle:
                on_disk = json.load(handle)
            self.assertEqual(on_disk["total_requests"], 1)
            self.assertEqual(on_disk["apis"]["key"]["models"]["gpt-5.4"]["total_tokens"], 3)


if __name__ == "__main__":
    unittest.main()
