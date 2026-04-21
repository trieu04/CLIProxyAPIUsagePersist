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

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return empty_snapshot()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return rebuild_snapshot(data)

    def save(self, snapshot: dict[str, Any]) -> None:
        normalized = rebuild_snapshot(snapshot)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as handle:
            json.dump(normalized, handle, indent=2, sort_keys=True)
            handle.write("\n")
            temp_name = handle.name
        os.replace(temp_name, self.path)
