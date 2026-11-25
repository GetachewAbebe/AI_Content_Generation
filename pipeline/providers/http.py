"""One place that maps HTTP outcomes onto the retry policy."""

from __future__ import annotations

from typing import Any

import requests

from ..core.errors import PermanentError, TransientError

TOO_MANY_REQUESTS = 429
SERVER_ERROR = 500
CLIENT_ERROR = 400


def post_json(url: str, *, timeout: float = 180, **kwargs: Any) -> dict[str, Any]:
    try:
        response = requests.post(url, timeout=timeout, **kwargs)
    except (requests.Timeout, requests.ConnectionError) as err:
        raise TransientError(f"{type(err).__name__}: {err}") from err
    detail = f"HTTP {response.status_code}: {response.text[:400]}"
    if response.status_code == TOO_MANY_REQUESTS or response.status_code >= SERVER_ERROR:
        after = response.headers.get("retry-after", "")
        raise TransientError(detail, float(after) if after.isdigit() else None)
    if response.status_code >= CLIENT_ERROR:
        raise PermanentError(detail)
    try:
        return response.json()
    except ValueError as err:
        raise TransientError("response was not JSON") from err
