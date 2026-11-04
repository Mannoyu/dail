import html
import re
from datetime import date as Date

from generator.template import render
from shared.models import DailyReport, MemberReport


def text(value: str) -> str:
    """Treat external strings as text in Markdown, including embedded HTML and links."""
    value = html.escape(value, quote=False).replace("\n", " ").replace("\r", " ")
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", value)


def generate(members: list[MemberReport], date: Date, team_name: str) -> DailyReport:
    report = DailyReport(date, team_name, members)
    return refresh(report)


def refresh(report: DailyReport) -> DailyReport:
    lines = [f"# {text(report.team_name)} · 工作日报", f"日期：{report.date}", ""]
    if report.demo:
        lines += ["> 演示数据，仅用于预览。", ""]
    if report.task_mode == "tasklist":
        lines += ["> 任务进展为当日任务清单的当前状态快照，不代表当日状态流转历史。", ""]
    statuses = {s.name: s.state for s in report.sources}
    sections = [("github", "代码提交"), ("tasks", "任务进展"), ("messages", "协作沟通")]
    for member in report.members:
        lines += [f"## {text(member.name)}", ""]
        for key, heading in sections:
            lines += [f"### {heading}", ""]
            if statuses.get(key) == "failed":
                lines += ["数据获取失败", ""]
                continue
            if statuses.get(key) == "disabled":
                lines += ["数据源未启用", ""]
                continue
            if key == "github":
                rows = [
                    f"- {text(r.message)} · {text(r.repo)} · "
                    f"+{r.additions}/-{r.deletions} · {r.files_changed} 个文件"
                    for r in member.commits
                ]
            elif key == "tasks":
                rows = [
                    f"- {text(r.title)} · "
                    + (
                        f"{text(r.status_from)} → {text(r.status_to)}"
                        if r.status_from
                        else f"当前状态：{text(r.status_to)}"
                    )
                    for r in member.tasks
                ]
            else:
                rows = [f"- {text(r.content)} · {text(r.chat_name)}" for r in member.messages]
            lines += (rows or ["当日无记录"]) + [""]
    report.markdown = "\n".join(lines)
    report.html = render(report)
    return report
