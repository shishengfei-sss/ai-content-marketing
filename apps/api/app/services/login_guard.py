"""登录失败计数与临时锁定（进程内，防暴力破解）。"""
from __future__ import annotations

import time
from threading import Lock

# phone -> (fail_count, locked_until_ts)
_failures: dict[str, tuple[int, float]] = {}
_lock = Lock()

MAX_FAILURES = 5
LOCK_SECONDS = 600


def is_locked(phone: str) -> bool:
    with _lock:
        entry = _failures.get(phone)
        if not entry:
            return False
        _, until = entry
        if until and until > time.time():
            return True
        if until and until <= time.time():
            _failures.pop(phone, None)
        return False


def record_failure(phone: str) -> tuple[bool, int]:
    """记录一次失败。返回 (是否已锁定, 当前失败次数)。"""
    with _lock:
        count, until = _failures.get(phone, (0, 0.0))
        if until and until > time.time():
            return True, count
        count += 1
        if count >= MAX_FAILURES:
            _failures[phone] = (count, time.time() + LOCK_SECONDS)
            return True, count
        _failures[phone] = (count, 0.0)
        return False, count


def clear_failures(phone: str) -> None:
    with _lock:
        _failures.pop(phone, None)
