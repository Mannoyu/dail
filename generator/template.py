from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

from shared.models import DailyReport

ENV = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html"]),
)


def render(report: DailyReport) -> str:
    return ENV.get_template("report.html").render(
        report=report,
        commits=sum(len(m.commits) for m in report.members),
        tasks=sum(len(m.tasks) for m in report.members),
        messages=sum(len(m.messages) for m in report.members),
        active=sum(bool(m.commits or m.tasks or m.messages) for m in report.members),
    )


def email_html(report: DailyReport) -> str:
    return (
        "<!doctype html><html lang='zh-CN'><meta charset='utf-8'>"
        "<body style='font-family:system-ui,sans-serif;line-height:1.8;color:#242424'>"
        + markdown.markdown(report.markdown)
        + "</body></html>"
    )
