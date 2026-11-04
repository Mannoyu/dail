from collections.abc import Callable
from datetime import datetime
from functools import wraps
from typing import ParamSpec, TypeVar

from shared.logger import get_logger

T = TypeVar("T")
P = ParamSpec("P")


class Collection(list[T]):
    """A list that preserves the distinction between an empty source and a failed source."""

    def __init__(self, records: list[T] | None = None, *, failed: bool = False):
        super().__init__(records or [])
        self.failed = failed


def guarded(fn: Callable[P, list[T]]) -> Callable[P, Collection[T]]:
    @wraps(fn)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> Collection[T]:
        try:
            return Collection(fn(*args, **kwargs))
        except Exception as exc:
            # Avoid exception messages: HTTP errors can embed credential-bearing URLs.
            get_logger(fn.__module__).error(f"数据获取失败 ({type(exc).__name__})")
            return Collection(failed=True)

    return wrapped


def check_window(since: datetime, until: datetime) -> None:
    if since.tzinfo is None or until.tzinfo is None or since > until:
        raise ValueError("采集窗口必须带时区，且 since <= until")


def parse_time(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("时间必须包含时区")
    return result
