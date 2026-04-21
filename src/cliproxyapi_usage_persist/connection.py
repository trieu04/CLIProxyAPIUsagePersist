"""Connection helpers mirroring the management center base URL behavior."""

from __future__ import annotations

import re

MANAGEMENT_API_PREFIX = "/v0/management"


def normalize_api_base(value: str) -> str:
    base = (value or "").strip()
    if not base:
        return ""
    base = re.sub(r"/?v0/management/?$", "", base, flags=re.IGNORECASE)
    base = re.sub(r"/+$", "", base)
    if not re.match(r"^https?://", base, flags=re.IGNORECASE):
        base = f"http://{base}"
    return base


def compute_management_url(value: str) -> str:
    normalized = normalize_api_base(value)
    if not normalized:
        return ""
    return f"{normalized}{MANAGEMENT_API_PREFIX}"
