from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from collector import github, lark_msg, lark_task
from collector.common import Collection
from generator.formatter import refresh
from notifier import email, lark_bot
from shared.config import Settings, configure
from shared.logger import get_logger
from shared.models import DailyReport, MemberReport, SourceStatus
from shared.storage import Storage

LOG = get_logger(__name__)


def write_report(report: DailyReport, output_dir: str) -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    # Each snapshot is self-contained; never serve the repo root or credential files.
    stem = report.date.isoformat() + ("-demo" if report.demo else "")
    for suffix, content in ((".md", report.markdown), (".html", report.html)):
        target = output / (stem + suffix)
        temp = target.with_suffix(suffix + ".tmp")
        temp.write_text(content, encoding="utf-8")
        temp.replace(target)
    return output / (stem + ".html")


def run(settings: Settings, now: datetime, *, dry_run: bool = False) -> DailyReport | None:
    configure(settings)
    since = (
        now - timedelta(hours=24)
        if settings.window == "rolling24h"
        else now.replace(hour=0, minute=0, second=0, microsecond=0)
    )
    specs: dict[str, tuple[bool, Any, tuple]] = {
        "github": (settings.github.enabled, github.collect, (settings.github.repos, since, now)),
        "tasks": (
            settings.lark.tasks_enabled,
            lark_task.collect,
            (settings.lark.project_id, since, now),
        ),
        "messages": (
            settings.lark.messages_enabled,
            lark_msg.collect,
            (settings.lark.chat_id, settings.lark.keywords, since, now),
        ),
    }
    records: dict[str, Any] = {}
    statuses = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            name: executor.submit(copy_context().run, fn, *args)
            for name, (enabled, fn, args) in specs.items()
            if enabled
        }
        for name, (enabled, _, _) in specs.items():
            if not enabled:
                statuses.append(SourceStatus(name, "disabled"))
                records[name] = []
                continue
            try:
                result = futures[name].result()
            except Exception:
                result = Collection(failed=True)
            failed = getattr(result, "failed", False)
            statuses.append(SourceStatus(name, "failed" if failed else "ok", len(result)))
            records[name] = [] if failed else result
            LOG.info(f"source={name} state={'failed' if failed else 'ok'} count={len(result)}")
    if not any(s.state == "ok" for s in statuses):
        LOG.error("所有启用的数据源不可用；不生成日报；请检查配置、权限和事件归档")
        return None
    members = [
        MemberReport(
            m.name,
            m.github,
            [r for r in records["github"] if r.author.casefold() == m.github.casefold()],
            [r for r in records["tasks"] if r.assignee == m.lark],
            [r for r in records["messages"] if r.sender == m.lark],
        )
        for m in settings.members
    ]
    mapped_count = sum(len(m.commits) + len(m.tasks) + len(m.messages) for m in members)
    raw_count = sum(len(r) for r in records.values())
    if raw_count != mapped_count:
        LOG.info(f"unmapped_records={raw_count - mapped_count}; 请检查账号映射")
    report = refresh(DailyReport(now.date(), settings.team_name, members, sources=statuses))
    Storage(settings.database).save(report)
    output = write_report(report, settings.output_dir)
    LOG.info(f"report_saved={output.name}")
    if dry_run:
        LOG.info("dry_run=true; 已生成日报，未执行推送")
        return report
    delivery: dict[str, bool] = {}
    if settings.email.enabled:
        delivery["email"] = email.send(report, settings.email.recipients)
    if settings.bot.enabled:
        delivery["bot"] = lark_bot.send(report, settings.bot.chat_id)
    for channel, success in delivery.items():
        LOG.info(f"delivery={channel} success={success}")
    if any(not success for success in delivery.values()):
        from shared.errors import NotifierError

        # Successful alternate channels already received the report; stderr is the fallback alert.
        LOG.error("推送失败；日报已保存在本地；请检查备用渠道和调度器告警")
        raise NotifierError("部分推送失败")
    return report
