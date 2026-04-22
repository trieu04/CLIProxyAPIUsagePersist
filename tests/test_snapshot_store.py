import json
import tempfile
import unittest
from pathlib import Path

from src.snapshot_store import SnapshotStore
from src.usage_merge import rebuild_snapshot


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

    def test_snapshot_store_skips_rewrite_when_normalized_content_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "usage.json"
            store = SnapshotStore(str(path))
            normalized = rebuild_snapshot(
                {
                    "apis": {
                        "key": {
                            "models": {
                                "gpt-5.4": {
                                    "details": [
                                        {
                                            "timestamp": "2026-03-20T12:00:00Z",
                                            "tokens": {"input_tokens": 1, "output_tokens": 2},
                                            "source": "",
                                            "auth_index": "",
                                            "failed": False,
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            )

            store.save(normalized, snapshot_already_normalized=True)
            original_text = path.read_text(encoding="utf-8")
            path.write_text(original_text, encoding="utf-8")

            store.save(normalized, snapshot_already_normalized=True)

            self.assertEqual(path.read_text(encoding="utf-8"), original_text)


if __name__ == "__main__":
    unittest.main()
