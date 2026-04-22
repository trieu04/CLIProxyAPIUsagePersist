"""Retry helpers for transient management API failures."""

from __future__ import annotations

import socket
import time
import urllib.error
from typing import Callable, TypeVar

T = TypeVar("T")


class ManagementApiError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, payload: object | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.payload = payload


def is_transient_failure(error: BaseException) -> bool:
    if isinstance(error, ManagementApiError):
        return error.status in {408, 425, 429} or (error.status is not None and error.status >= 500)
    if isinstance(error, urllib.error.HTTPError):
        return error.code in {408, 425, 429} or error.code >= 500
    return isinstance(error, (TimeoutError, socket.timeout, urllib.error.URLError, ConnectionError))


def retry_call(
    operation: Callable[[], T],
    *,
    attempts: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    if attempts <= 0:
        raise ValueError("attempts must be greater than zero")
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except BaseException as error:  # pragma: no cover - exercised through tests
            last_error = error
            if attempt >= attempts or not is_transient_failure(error):
                raise
            delay = min(max_delay_seconds, base_delay_seconds * (2 ** (attempt - 1)))
            sleep(delay)
    assert last_error is not None
    raise last_error
