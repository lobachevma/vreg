"""Проверка доступности видеорегистраторов по TCP."""

from __future__ import annotations

import socket
import time
from typing import Dict, Tuple

RECORDER_CHECK_PORTS = (80, 554, 8000)
CONNECT_TIMEOUT_SEC = 1.0
CACHE_TTL_SEC = 60

_cache: Dict[int, Tuple[float, bool]] = {}


def is_recorder_reachable(ip_address: str | None) -> bool:
    if not ip_address or not str(ip_address).strip():
        return False

    host = str(ip_address).strip()
    for port in RECORDER_CHECK_PORTS:
        try:
            with socket.create_connection((host, port), timeout=CONNECT_TIMEOUT_SEC):
                return True
        except OSError:
            continue
    return False


def recorder_online_cached(recorder_id: int, ip_address: str | None) -> bool:
    now = time.monotonic()
    cached = _cache.get(recorder_id)
    if cached is not None:
        cached_at, value = cached
        if now - cached_at < CACHE_TTL_SEC:
            return value

    online = is_recorder_reachable(ip_address)
    _cache[recorder_id] = (now, online)
    return online
