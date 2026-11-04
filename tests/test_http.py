import httpx
import pytest

from shared.errors import CollectorError
from shared.http import APIClient


def test_slow_stream_stops_at_budget_and_closes(cfg, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("shared.http.time.monotonic", lambda: clock[0])

    class SlowBody(httpx.SyncByteStream):
        closed = False

        def __iter__(self):
            for _ in range(10):
                clock[0] += 10
                yield b" "

        def close(self):
            self.closed = True

    body = SlowBody()
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=body))
    ) as client:
        with APIClient(client) as api, pytest.raises(CollectorError, match="执行超时"):
            api.request("GET", "https://example.com")
    assert body.closed and clock[0] == 50
