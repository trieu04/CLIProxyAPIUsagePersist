"""Environment-backed runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .connection import compute_management_url


@dataclass(frozen=True)
class AppConfig:
    api_base: str
    management_key: str
    snapshot_path: str = "/data/usage-snapshot.json"
    interval_seconds: int = 3600
    timeout_seconds: float = 15.0
    retry_attempts: int = 4
    retry_base_delay_seconds: float = 1.0
    retry_max_delay_seconds: float = 8.0

    @property
    def management_url(self) -> str:
        return compute_management_url(self.api_base)


def _read_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    value = int(raw)
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _read_float(name: str, default: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    value = float(raw)
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def load_config() -> AppConfig:
    api_base = os.getenv("CLIPROXYAPI_BASE_URL", "").strip()
    management_key = os.getenv("CLIPROXYAPI_MANAGEMENT_KEY", "").strip()
    if not api_base:
        raise ValueError("CLIPROXYAPI_BASE_URL is required")
    if not management_key:
        raise ValueError("CLIPROXYAPI_MANAGEMENT_KEY is required")

    return AppConfig(
        api_base=api_base,
        management_key=management_key,
        snapshot_path=os.getenv("USAGE_SNAPSHOT_PATH", "/data/usage-snapshot.json").strip()
        or "/data/usage-snapshot.json",
        interval_seconds=_read_int("SYNC_INTERVAL_SECONDS", 3600),
        timeout_seconds=_read_float("HTTP_TIMEOUT_SECONDS", 15.0),
        retry_attempts=_read_int("RETRY_ATTEMPTS", 4),
        retry_base_delay_seconds=_read_float("RETRY_BASE_DELAY_SECONDS", 1.0),
        retry_max_delay_seconds=_read_float("RETRY_MAX_DELAY_SECONDS", 8.0),
    )
