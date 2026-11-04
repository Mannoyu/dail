"""Read exact task transitions from an upstream Feishu project event archive.

The ordinary Task v2 list API exposes current task state, not status history.
Do not manufacture transitions from `updated_at` or infer previous status.
"""

import json
import time
from datetime import datetime
from pathlib import Path

from collector.common import check_window, guarded, parse_time
from shared.config import get_config
from shared.errors import CollectorError
from shared.models import TaskRecord


@guarded
def collect(project_id: str, since: datetime, until: datetime) -> list[TaskRecord]:
    check_window(since, until)
    cfg = get_config()
    if project_id != cfg.lark.project_id:
        raise CollectorError("项目不在白名单内")
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
