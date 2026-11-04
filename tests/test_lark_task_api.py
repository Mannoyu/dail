from datetime import timedelta

import httpx

from collector.lark_task import collect


def install_api(cfg, now, mock_http, monkeypatch, *, expired=False, loop=False):
    cfg.lark.task_mode = "tasklist"
    monkeypatch.setattr("collector.lark_task._today", lambda: now.date())
    calls = []
    auths = []

    def handler(request):
        calls.append(request)
        path = request.url.path
        if path.endswith("tenant_access_token/internal"):
            auths.append(1)
            return httpx.Response(200, json={"code": 0, "tenant_access_token": f"t{len(auths)}"})
        assert request.url.params["user_id_type"] == "open_id"
        if expired and len(auths) == 1:
            return httpx.Response(200, json={"code": 99991663})
        if path.endswith("/tasklists/project/tasks"):
            if "page_token" not in request.url.params:
                data = {"items": [{"guid": "other"}], "has_more": True, "page_token": "next"}
            else:
                data = {"items": [{"guid": "parent"}], "has_more": loop, "page_token": "next"}
        elif path.endswith("/subtasks"):
            guid = path.split("/")[-2]
            children = {"parent": ["a", "b", "a"], "a": ["nested"], "nested": ["parent"]}
            data = {"items": [{"guid": g} for g in children.get(guid, [])]}
        else:
            guid = path.split("/")[-1]
            data = {
                "task": {
                    "summary": f"{now.month}月{now.day}日任务清单" if guid == "parent" else guid,
                    "updated_at": str(int(now.timestamp() * 1000)),
                    "completed_at": str(int(now.timestamp() * 1000)) if guid == "a" else "0",
                    "members": [
                        {"role": "follower", "id": "ou_follower"},
                        {"role": "assignee", "id": "ou_alice"},
                        {"role": "assignee", "id": "ou_bob"},
                    ],
                }
            }
        return httpx.Response(200, json={"code": 0, "data": data})

    mock_http(handler)
    return calls, auths


def test_tasklist_snapshots_pages_descendants_assignees_and_token_refresh(
    cfg, now, mock_http, monkeypatch
):
    calls, auths = install_api(cfg, now, mock_http, monkeypatch, expired=True)
    result = collect("project", now - timedelta(hours=18), now)
    assert not result.failed and len(result) == 6
    assert {r.title for r in result} == {"a", "b", "nested"}
    assert {r.assignee for r in result} == {"ou_alice", "ou_bob"}
    assert all(r.status_from == "" for r in result)
    assert {r.status_to for r in result if r.title == "a"} == {"已完成"}
    assert len(auths) == 2
    assert all(r.method == "GET" or "auth/" in r.url.path for r in calls)


def test_tasklist_repeated_cursor_fails(cfg, now, mock_http, monkeypatch):
    install_api(cfg, now, mock_http, monkeypatch, loop=True)
    assert collect("project", now - timedelta(hours=18), now).failed


def test_snapshot_historical_rerun_is_rejected(cfg, now, monkeypatch):
    cfg.lark.task_mode = "tasklist"
    monkeypatch.setattr("collector.lark_task._today", lambda: now.date() + timedelta(days=1))
    assert collect("project", now - timedelta(hours=18), now).failed


def test_tasklist_timeout_retries(cfg, now, mock_http, monkeypatch):
    cfg.lark.task_mode = "tasklist"
    monkeypatch.setattr("collector.lark_task._today", lambda: now.date())
    calls = []

    def handler(request):
        calls.append(1)
        raise httpx.ReadTimeout("timeout", request=request)

    mock_http(handler)
    assert collect("project", now - timedelta(hours=18), now).failed
    assert len(calls) == 4


def test_missing_daily_parent_is_empty_success(cfg, now, mock_http, monkeypatch):
    cfg.lark.task_mode = "tasklist"
    monkeypatch.setattr("collector.lark_task._today", lambda: now.date())

    def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json={"code": 0, "tenant_access_token": "t"})
        return httpx.Response(200, json={"code": 0, "data": {"items": []}})

    mock_http(handler)
    result = collect("project", now - timedelta(hours=18), now)
    assert result == [] and not result.failed


def test_tasklist_health_reads_api_without_delivering(cfg, mock_http):
    from shared.health import check

    cfg.github.enabled = cfg.lark.messages_enabled = False
    cfg.lark.task_mode = "tasklist"
    calls = []

    def handler(request):
        calls.append(request)
        if request.method == "POST":
            return httpx.Response(200, json={"code": 0, "tenant_access_token": "t"})
        assert request.url.path.endswith("/tasklists/project/tasks")
        return httpx.Response(200, json={"code": 0, "data": {"items": []}})

    mock_http(handler)
    assert check(cfg) and len(calls) == 2
