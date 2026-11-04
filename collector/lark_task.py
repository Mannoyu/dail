"""Read Task v2 daily tasklist snapshots or exact archived transition events."""

import json
import time
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from collector.common import check_window, guarded, parse_time
from collector.lark_client import LarkClient
from shared.config import get_config
from shared.errors import CollectorError
from shared.http import APIClient
from shared.models import TaskRecord


@guarded
def collect(project_id: str, since: datetime, until: datetime) -> list[TaskRecord]:
    check_window(since, until)
    cfg = get_config()
    if project_id != cfg.lark.project_id:
        raise CollectorError("项目不在白名单内")
    if cfg.lark.task_mode == "tasklist":
        return _collect_tasklist(project_id, until)
    path = Path(cfg.lark.task_events)
    if not path.is_file():
        raise CollectorError("未配置飞书项目事件归档；不能用任务快照冒充状态流转")
    records = []
    seen = set()
    deadline = time.monotonic() + cfg.http.source_deadline
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if time.monotonic() > deadline:
                raise CollectorError("事件归档读取超时")
            if not line.strip():
                continue
            event = json.loads(line)
            if event["project_id"] != project_id:
                continue
            values = [event[k] for k in ("assignee", "title", "status_from", "status_to")]
            if not all(isinstance(v, str) and v for v in values):
                raise CollectorError("事件字段类型错误")
            timestamp = parse_time(event["updated_at"])
            event_id = event.get("event_id")
            if event_id is not None and (not isinstance(event_id, str) or not event_id):
                raise CollectorError("event_id 必须为非空字符串")
            # Display fields cannot identify an event: distinct tasks may look identical.
            if since <= timestamp <= until and (event_id is None or event_id not in seen):
                if event_id is not None:
                    seen.add(event_id)
                records.append(TaskRecord(values[0], values[1], values[2], values[3], timestamp))
    return sorted(records, key=lambda r: r.updated_at)


def _today() -> date:
    return datetime.now(ZoneInfo(get_config().timezone)).date()


def _items(client: LarkClient, path: str):
    token = ""
    seen = set()
    while True:
        params: dict = {"page_size": 50, "user_id_type": "open_id"}
        if token:
            params["page_token"] = token
        data = client.get(path, params)
        items = data.get("items", [])
        if not isinstance(items, list):
            raise CollectorError("飞书任务列表格式错误")
        yield from items
        if not data.get("has_more"):
            return
        token = data.get("page_token", "")
        if not token or token in seen:
            raise CollectorError("飞书任务分页游标未推进")
        seen.add(token)


def _collect_tasklist(project_id: str, until: datetime) -> list[TaskRecord]:
    day = until.astimezone(ZoneInfo(get_config().timezone)).date()
    if day != _today():
        raise CollectorError("Task v2 当前快照不支持历史补跑；请改用事件归档")
    name = f"{day.month}月{day.day}日任务清单"
    records = []
    seen = set()
    with APIClient() as api:
        client = LarkClient(api)

        def detail(guid: str) -> dict:
            data = client.get("/task/v2/tasks/" + quote(guid, safe=""), {"user_id_type": "open_id"})
            task = data["task"]
            if not isinstance(task, dict):
                raise CollectorError("飞书任务详情格式错误")
            return task

        parents = []
        for slim in _items(client, "/task/v2/tasklists/" + quote(project_id, safe="") + "/tasks"):
            guid = slim["guid"]
            if detail(guid).get("summary") == name:
                parents.append(guid)

        # Iterative traversal avoids recursion limits; GUID dedup handles repeated
        # pages, shared children and malformed cycles without double counting.
        pending = list(parents)
        seen.update(parents)
        while pending:
            parent = pending.pop()
            for slim in _items(client, "/task/v2/tasks/" + quote(parent, safe="") + "/subtasks"):
                guid = slim["guid"]
                if guid in seen:
                    continue
                seen.add(guid)
                task = detail(guid)
                pending.append(guid)
                completed = int(task.get("completed_at") or 0)
                stamp = next(
                    (
                        int(task[k])
                        for k in ("completed_at", "updated_at", "created_at")
                        if int(task.get(k) or 0) > 0
                    ),
                    0,
                )
                if not stamp:
                    raise CollectorError("飞书任务缺少有效时间戳")
                assignees = set()
                for member in task.get("members", []):
                    if (
                        member.get("role") == "assignee"
                        and member.get("id")
                        and member.get("type", "user") == "user"
                        and member["id"] not in assignees
                    ):
                        assignees.add(member["id"])
                        records.append(
                            TaskRecord(
                                member["id"],
                                task["summary"],
                                "",
                                "已完成" if completed > 0 else "进行中",
                                datetime.fromtimestamp(stamp / 1000, tz=UTC),
                            )
                        )
    return sorted(records, key=lambda r: (r.updated_at, r.title, r.assignee))
