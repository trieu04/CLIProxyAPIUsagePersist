"""Server-compatible usage snapshot normalization and merging."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

EMPTY_SNAPSHOT: dict[str, Any] = {
    "total_requests": 0,
    "success_count": 0,
    "failure_count": 0,
    "total_tokens": 0,
    "apis": {},
    "requests_by_day": {},
    "requests_by_hour": {},
    "tokens_by_day": {},
    "tokens_by_hour": {},
}

__all__ = [
    "empty_snapshot",
    "normalize_token_stats",
    "detail_key",
    "rebuild_snapshot",
    "merge_snapshots",
    "unique_request_count",
    "deduped_unique_request_count",
    "_canonical_timestamp",
]


def empty_snapshot() -> dict[str, Any]:
    return {key: (value.copy() if isinstance(value, dict) else value) for key, value in EMPTY_SNAPSHOT.items()}


def _finalize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    for api_snapshot in snapshot["apis"].values():
        for model_snapshot in api_snapshot["models"].values():
            for detail in model_snapshot["details"]:
                detail.pop("_hour", None)
    return snapshot


def normalize_token_stats(tokens: dict[str, Any] | None) -> dict[str, int]:
    data = dict(tokens or {})
    normalized = {
        "input_tokens": int(data.get("input_tokens", 0) or 0),
        "output_tokens": int(data.get("output_tokens", 0) or 0),
        "reasoning_tokens": int(data.get("reasoning_tokens", 0) or 0),
        "cached_tokens": int(data.get("cached_tokens", 0) or 0),
        "total_tokens": int(data.get("total_tokens", 0) or 0),
    }
    if normalized["total_tokens"] == 0:
        normalized["total_tokens"] = (
            normalized["input_tokens"]
            + normalized["output_tokens"]
            + normalized["reasoning_tokens"]
        )
    if normalized["total_tokens"] == 0:
        normalized["total_tokens"] = (
            normalized["input_tokens"]
            + normalized["output_tokens"]
            + normalized["reasoning_tokens"]
            + normalized["cached_tokens"]
        )
    return normalized


def _canonical_timestamp(value: Any, fallback: datetime | None = None) -> tuple[str, datetime]:
    if isinstance(value, datetime):
        dt = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
        text = dt.isoformat().replace("+00:00", "Z")
        return text, dt
    raw = str(value or "").strip()
    if not raw:
        dt = (fallback or datetime.now(timezone.utc)).astimezone(timezone.utc)
        text = dt.isoformat().replace("+00:00", "Z")
        return text, dt
    raw = raw.replace("z", "Z")
    if raw.endswith("Z"):
        parseable = f"{raw[:-1]}+00:00"
    elif len(raw) > 6 and raw[-6] in "+-" and raw[-3] == ":":
        parseable = raw
    else:
        parseable = f"{raw}+00:00"
    fraction = ""
    main = parseable
    sign_index = max(parseable.rfind("+"), parseable.rfind("-"))
    if sign_index > 10:
        main = parseable[:sign_index]
        suffix = parseable[sign_index:]
    else:
        suffix = "+00:00"
    if "." in main:
        main, fraction = main.split(".", 1)
    nanos = (fraction + "000000000")[:9]
    dt = datetime.fromisoformat(f"{main}.{nanos[:6]}{suffix}").astimezone(timezone.utc)
    dt += timedelta(microseconds=0)
    seconds = dt.strftime("%Y-%m-%dT%H:%M:%S")
    trimmed = nanos.rstrip("0")
    text = f"{seconds}.{trimmed}Z" if trimmed else f"{seconds}Z"
    return text, dt


def _append_detail(target: dict[str, Any], api_name: str, model_name: str, detail: dict[str, Any]) -> None:
    api_snapshot = target["apis"].setdefault(api_name, {"total_requests": 0, "total_tokens": 0, "models": {}})
    model_snapshot = api_snapshot["models"].setdefault(model_name, {"total_requests": 0, "total_tokens": 0, "details": []})
    tokens = detail["tokens"]
    total_tokens = tokens["total_tokens"]

    target["total_requests"] += 1
    if detail["failed"]:
        target["failure_count"] += 1
    else:
        target["success_count"] += 1
    target["total_tokens"] += total_tokens
    api_snapshot["total_requests"] += 1
    api_snapshot["total_tokens"] += total_tokens
    model_snapshot["total_requests"] += 1
    model_snapshot["total_tokens"] += total_tokens
    model_snapshot["details"].append(detail)

    day_key = detail["timestamp"][:10]
    hour_key = f"{detail['_hour']:02d}"
    target["requests_by_day"][day_key] = target["requests_by_day"].get(day_key, 0) + 1
    target["requests_by_hour"][hour_key] = target["requests_by_hour"].get(hour_key, 0) + 1
    target["tokens_by_day"][day_key] = target["tokens_by_day"].get(day_key, 0) + total_tokens
    target["tokens_by_hour"][hour_key] = target["tokens_by_hour"].get(hour_key, 0) + total_tokens


def _iter_snapshot_details(
    snapshot: dict[str, Any] | None,
    *,
    already_normalized: bool = False,
    now: datetime | None = None,
):
    current = now or datetime.now(timezone.utc)
    for raw_api_name, api_snapshot in dict((snapshot or {}).get("apis", {})).items():
        api_name = str(raw_api_name or "").strip()
        if not api_name:
            continue
        models = dict((api_snapshot or {}).get("models", {}))
        for raw_model_name, model_snapshot in models.items():
            model_name = str(raw_model_name or "").strip() or "unknown"
            for raw_detail in list((model_snapshot or {}).get("details", [])):
                detail = dict(raw_detail or {})
                if already_normalized:
                    timestamp_text = str(detail.get("timestamp", "") or "")
                    normalized = {
                        "timestamp": timestamp_text,
                        "latency_ms": max(int(detail.get("latency_ms", 0) or 0), 0),
                        "source": str(detail.get("source", "") or ""),
                        "auth_index": str(detail.get("auth_index", "") or ""),
                        "tokens": normalize_token_stats(detail.get("tokens")),
                        "failed": bool(detail.get("failed", False)),
                        "_hour": int(timestamp_text[11:13]),
                    }
                else:
                    timestamp_text, timestamp_dt = _canonical_timestamp(detail.get("timestamp"), current)
                    normalized = {
                        "timestamp": timestamp_text,
                        "latency_ms": max(int(detail.get("latency_ms", 0) or 0), 0),
                        "source": str(detail.get("source", "") or ""),
                        "auth_index": str(detail.get("auth_index", "") or ""),
                        "tokens": normalize_token_stats(detail.get("tokens")),
                        "failed": bool(detail.get("failed", False)),
                        "_hour": timestamp_dt.hour,
                    }
                yield api_name, model_name, normalized


def detail_key(api_name: str, model_name: str, detail: dict[str, Any]) -> str:
    tokens = detail["tokens"]
    parts = [
        api_name,
        model_name,
        detail["timestamp"],
        detail["source"],
        detail["auth_index"],
        "true" if detail["failed"] else "false",
        str(tokens["input_tokens"]),
        str(tokens["output_tokens"]),
        str(tokens["reasoning_tokens"]),
        str(tokens["cached_tokens"]),
        str(tokens["total_tokens"]),
    ]
    return "|".join(parts)


def rebuild_snapshot(snapshot: dict[str, Any] | None, *, now: datetime | None = None) -> dict[str, Any]:
    result = empty_snapshot()
    for api_name, model_name, detail in _iter_snapshot_details(snapshot, now=now):
        _append_detail(result, api_name, model_name, detail)
    return _finalize_snapshot(result)


def merge_snapshots(
    base: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
    *,
    inputs_already_normalized: bool = False,
) -> tuple[dict[str, Any], dict[str, int]]:
    merged = empty_snapshot()
    counts = {"added": 0, "skipped": 0}
    seen: set[str] = set()
    for source in (base, incoming):
        for api_name, model_name, detail in _iter_snapshot_details(
            source,
            already_normalized=inputs_already_normalized,
        ):
            key = detail_key(api_name, model_name, detail)
            if key in seen:
                counts["skipped"] += 1
                continue
            seen.add(key)
            _append_detail(merged, api_name, model_name, detail)
            counts["added"] += 1
    return _finalize_snapshot(merged), counts


def unique_request_count(snapshot: dict[str, Any] | None, *, snapshot_already_normalized: bool = False) -> int:
    rebuilt = snapshot if snapshot_already_normalized and snapshot is not None else rebuild_snapshot(snapshot)
    return sum(
        len(model_snapshot["details"])
        for api_snapshot in rebuilt["apis"].values()
        for model_snapshot in api_snapshot["models"].values()
    )


def deduped_unique_request_count(snapshot: dict[str, Any] | None, *, snapshot_already_normalized: bool = False) -> int:
    rebuilt = snapshot if snapshot_already_normalized and snapshot is not None else rebuild_snapshot(snapshot)
    seen: set[str] = set()
    for api_name, api_snapshot in rebuilt["apis"].items():
        for model_name, model_snapshot in api_snapshot["models"].items():
            for detail in model_snapshot["details"]:
                seen.add(detail_key(api_name, model_name, detail))
    return len(seen)
