"""Atomic on-disk snapshot persistence."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .usage_merge import empty_snapshot, rebuild_snapshot


class SnapshotStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    @staticmethod
    def _serialize(snapshot: dict[str, Any]) -> str:
        return json.dumps(snapshot, indent=2, sort_keys=True) + "\n"

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return empty_snapshot()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return rebuild_snapshot(data)

    def save(self, snapshot: dict[str, Any], *, snapshot_already_normalized: bool = False) -> None:
        normalized = snapshot if snapshot_already_normalized else rebuild_snapshot(snapshot)
        serialized = self._serialize(normalized)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and self.path.read_text(encoding="utf-8") == serialized:
            return
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as handle:
            handle.write(serialized)
            temp_name = handle.name
        os.replace(temp_name, self.path)
