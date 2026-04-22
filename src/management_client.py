"""CLIProxyAPI management API client."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable, Protocol

from .retry import ManagementApiError


class ResponseLike(Protocol):
    def read(self) -> bytes: ...

    def close(self) -> None: ...


Sender = Callable[[urllib.request.Request, float], ResponseLike]


def _default_sender(request: urllib.request.Request, timeout: float) -> ResponseLike:
    return urllib.request.urlopen(request, timeout=timeout)


class ManagementClient:
    def __init__(
        self,
        *,
        base_url: str,
        management_key: str,
        timeout_seconds: float,
        sender: Sender = _default_sender,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.management_key = management_key
        self.timeout_seconds = timeout_seconds
        self.sender = sender

    def export_usage_snapshot(self) -> dict[str, object]:
        payload = self._request_json("GET", "/usage/export")
        if "usage" not in payload:
            raise ManagementApiError("export response missing usage payload", payload=payload)
        return payload

    def import_usage_snapshot(self, snapshot: dict[str, object]) -> dict[str, object]:
        return self._request_json("POST", "/usage/import", {"version": 1, "usage": snapshot})

    def _request_json(self, method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url=f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.management_key}",
            },
        )
        try:
            response = self.sender(request, self.timeout_seconds)
            try:
                data = response.read()
            finally:
                close = getattr(response, "close", None)
                if callable(close):
                    close()
        except urllib.error.HTTPError as error:
            message, payload = _decode_error(error.read())
            raise ManagementApiError(message, status=error.code, payload=payload) from error
        except urllib.error.URLError as error:
            reason = getattr(error, "reason", error)
            raise ConnectionError(str(reason)) from error
        try:
            decoded = json.loads(data.decode("utf-8") or "{}")
        except json.JSONDecodeError as error:
            raise ManagementApiError("management API returned invalid json") from error
        if not isinstance(decoded, dict):
            raise ManagementApiError("management API returned non-object json", payload=decoded)
        return {str(key): value for key, value in decoded.items()}


def _decode_error(raw: bytes) -> tuple[str, dict[str, object] | None]:
    if not raw:
        return "management API request failed", None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        text = raw.decode("utf-8", errors="replace").strip()
        return text or "management API request failed", None
    if isinstance(payload, dict):
        normalized = {str(key): value for key, value in payload.items()}
        message = normalized.get("error") or normalized.get("message") or "management API request failed"
        return str(message), normalized
    return "management API request failed", None
