import json
import time
from collections.abc import Callable
from typing import Any

import httpx

from shared.config import get_config
from shared.errors import CollectorError


class APIClient:
    """Check source budget between requests and chunks without logging secrets.

    A blocking socket phase may overrun the budget by its timeout. This is a
    cooperative deadline, not a process-level hard timeout.
    """

    def __init__(
        self, client: httpx.Client | None = None, sleep: Callable[[float], None] = time.sleep
    ):
        self.policy = get_config().http
        self.client = client or httpx.Client(follow_redirects=False)
        self.owned = client is None
        self.sleep = sleep
        self.deadline = time.monotonic() + self.policy.source_deadline

    def __enter__(self) -> "APIClient":
        return self

    def __exit__(self, *args: Any) -> None:
        if self.owned:
            self.client.close()

    def wait(self, delay: float) -> None:
        if delay > self.policy.max_rate_wait or time.monotonic() + delay >= self.deadline:
            raise CollectorError("数据源超出等待预算")
        self.sleep(max(0, delay))

    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        for attempt in range(self.policy.retries + 1):
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise CollectorError("数据源执行超时")
            try:
                with self.client.stream(
                    method,
                    url,
                    timeout=min(self.policy.timeout, remaining),
                    **kwargs,
                ) as response:
                    rate_limited = response.status_code == 429 or (
                        response.status_code == 403
                        and (
                            response.headers.get("x-ratelimit-remaining") == "0"
                            or "retry-after" in response.headers
                        )
                    )
                    if rate_limited:
                        if attempt == self.policy.retries:
                            raise CollectorError("API 限流重试耗尽")
                        delay = float(response.headers.get("retry-after", "0"))
                        reset = float(response.headers.get("x-ratelimit-reset", "0"))
                        self.wait(max(delay, reset - time.time(), self.policy.retry_interval))
                        continue
                    if response.status_code >= 500:
                        raise httpx.ReadError("上游服务不可用")
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        if time.monotonic() >= self.deadline:
                            raise CollectorError("数据源执行超时")
                        body.extend(chunk)
                    if time.monotonic() >= self.deadline:
                        raise CollectorError("数据源执行超时")
                    return json.loads(body)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt == self.policy.retries:
                    raise CollectorError("API 请求重试耗尽") from exc
                self.wait(self.policy.retry_interval)
            except (httpx.HTTPStatusError, ValueError, TypeError) as exc:
                raise CollectorError("API 响应无效或权限不足") from exc
        raise CollectorError("API 请求失败")
