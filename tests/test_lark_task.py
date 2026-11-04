import json
from datetime import timedelta
from pathlib import Path

from collector.lark_task import collect


def test_exact_events_window_project_and_dedup(cfg, now):
    event = {
        "event_id": "event-1",
        "project_id": "project",
        "assignee": "ou_alice",
        "title": "测试",
        "status_from": "进行中",
        "status_to": "完成",
        "updated_at": now.isoformat(),
    }
    events = [
        event,
        event,
        {**event, "project_id": "other"},
        {**event, "updated_at": (now - timedelta(days=2)).isoformat()},
    ]
    Path(cfg.lark.task_events).write_text(
        "\n".join(json.dumps(e) for e in events), encoding="utf-8"
    )
    records = collect("project", now - timedelta(days=1), now)
    assert len(records) == 1 and records[0].status_from == "进行中"


def test_missing_event_archive_is_failed_not_empty(cfg, now):
    assert collect("project", now - timedelta(days=1), now).failed


def test_identical_transitions_without_event_identity_are_preserved(cfg, now):
    event = {
        "project_id": "project",
        "assignee": "ou_alice",
        "title": "同名任务",
        "status_from": "进行中",
        "status_to": "完成",
        "updated_at": now.isoformat(),
    }
    Path(cfg.lark.task_events).write_text(
        "\n".join(json.dumps({**event, "task_id": task}) for task in ["a", "b"]),
        encoding="utf-8",
    )
    assert len(collect("project", now - timedelta(days=1), now)) == 2
