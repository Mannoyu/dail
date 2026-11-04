from datetime import timedelta

import httpx

from collector.github import collect


def detail(now, author="alice"):
    return {
        "author": {"login": author},
        "commit": {
            "message": "fix: test",
            "author": {"email": "a@example.com"},
            "committer": {"date": now.isoformat()},
        },
        "stats": {"additions": 10, "deletions": 2},
        "files": [{"filename": "a.py"}],
    }


def test_pagination_stats_and_dedup(cfg, now, mock_http):
    pages = []

    def handler(request):
        if request.url.path.endswith("/branches"):
            return httpx.Response(200, json=[{"commit": {"sha": "main"}}])
        if request.url.path.endswith("/commits"):
            page = int(request.url.params["page"])
            pages.append(page)
            batch = [{"sha": str(i)} for i in range(100)] if page == 1 else [{"sha": "100"}]
            return httpx.Response(200, json=batch)
        return httpx.Response(200, json=detail(now))

    mock_http(handler)
    records = collect(["org/repo", "org/repo"], now - timedelta(days=1), now)
    assert len(records) == 101 and pages == [1, 2] and not records.failed
    assert records[0].additions == 10 and records[0].files_changed == 1
    assert records[0].timestamp == now


def test_timeout_retries_and_failure_not_empty_success(cfg, now, mock_http):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("contains-sensitive-url", request=request)

    mock_http(handler)
    records = collect(["org/repo"], now - timedelta(days=1), now)
    assert records == [] and records.failed and len(calls) == 4


def test_rate_limit_wait_and_permission_denied(cfg, now, mock_http, monkeypatch):
    calls = []
    waits = []
    monkeypatch.setattr("shared.http.time.sleep", waits.append)
    # APIClient default sleep is bound at function definition; inject it explicitly.
    from shared.http import APIClient

    monkeypatch.setattr("collector.github.APIClient", lambda: APIClient(sleep=waits.append))

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(403, headers={"x-ratelimit-remaining": "0", "retry-after": "1"})
        return httpx.Response(200, json=[])

    mock_http(handler)
    result = collect(["org/repo"], now - timedelta(days=1), now)
    assert not result.failed and waits == [1] and len(calls) == 2
    mock_http(lambda request: httpx.Response(403, json={"message": "forbidden"}))
    assert collect(["org/repo"], now - timedelta(days=1), now).failed


def test_huge_rate_reset_fails_within_budget(cfg, now, mock_http):
    mock_http(lambda request: httpx.Response(429, headers={"retry-after": "3600"}))
    assert collect(["org/repo"], now - timedelta(days=1), now).failed


def test_detail_failure_does_not_return_partial_success(cfg, now, mock_http):
    def handler(request):
        if request.url.path.endswith("/branches"):
            return httpx.Response(200, json=[{"commit": {"sha": "main"}}])
        if request.url.path.endswith("/commits"):
            return httpx.Response(200, json=[{"sha": "a"}, {"sha": "b"}])
        return (
            httpx.Response(200, json=detail(now))
            if request.url.path.endswith("/a")
            else httpx.Response(404)
        )

    mock_http(handler)
    result = collect(["org/repo"], now - timedelta(days=1), now)
    assert result == [] and result.failed


def test_branch_dedup_and_file_pagination(cfg, now, mock_http):
    detail_calls = []

    def handler(request):
        if request.url.path.endswith("/branches"):
            return httpx.Response(200, json=[{"commit": {"sha": b}} for b in ["main", "dev"]])
        if request.url.path.endswith("/commits"):
            return httpx.Response(200, json=[{"sha": "shared"}])
        page = int(request.url.params.get("page", 1))
        detail_calls.append(page)
        payload = detail(now)
        payload["files"] = [{}] * (100 if page == 1 else 7)
        return httpx.Response(200, json=payload)

    mock_http(handler)
    result = collect(["org/repo"], now - timedelta(days=1), now)
    assert not result.failed and len(result) == 1
    assert result[0].files_changed == 107 and detail_calls == [1, 2]
