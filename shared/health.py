import smtplib
from pathlib import Path
from urllib.parse import urlparse

from collector.lark_client import LarkClient
from notifier.email import connect
from shared.config import Settings, configure, secret
from shared.http import APIClient
from shared.logger import get_logger


def check(settings: Settings) -> bool:
    """Read-only API checks. Never sends messages or test emails."""
    configure(settings)
    checks = []
    if settings.github.enabled:

        def github_check() -> None:
            with APIClient() as api:
                for repo in settings.github.repos:
                    api.request(
                        "GET",
                        f"https://api.github.com/repos/{repo}/commits",
                        params={
                            "per_page": 1,
                        },
                        headers={"Authorization": f"Bearer {secret(settings.github.token_env)}"},
                    )

        checks.append(("github", github_check))
    if settings.lark.messages_enabled:

        def message_check() -> None:
            with APIClient() as api:
                LarkClient(api).get(
                    "/im/v1/messages",
                    {
                        "container_id_type": "chat",
                        "container_id": settings.lark.chat_id,
                        "page_size": 1,
                    },
                )

        checks.append(("messages", message_check))
    if settings.lark.tasks_enabled:

        def task_check() -> None:
            if settings.lark.task_mode == "events":
                path = Path(settings.lark.task_events)
                with path.open(encoding="utf-8") as stream:
                    stream.read(1)
            else:
                from urllib.parse import quote

                with APIClient() as api:
                    LarkClient(api).get(
                        "/task/v2/tasklists/" + quote(settings.lark.project_id, safe="") + "/tasks",
                        {"page_size": 1, "user_id_type": "open_id"},
                    )

        checks.append(("tasks_" + settings.lark.task_mode, task_check))
    if settings.email.enabled:

        def email_check() -> None:
            with connect() as smtp:
                code, _ = smtp.noop()
                if code != 250:
                    raise smtplib.SMTPException("NOOP failed")

        checks.append(("smtp", email_check))
    if settings.bot.enabled:

        def bot_check() -> None:
            url = urlparse(secret(settings.bot.webhook_env))
            if url.scheme != "https" or not url.hostname or not url.path:
                raise ValueError("webhook 地址无效")

        checks.append(("bot_config_only_not_delivery", bot_check))
    ok = bool(checks)
    for name, fn in checks:
        try:
            fn()
            get_logger(__name__).info(f"health={name} ok=true")
        except Exception as exc:
            ok = False
            get_logger(__name__).error(f"health={name} ok=false type={type(exc).__name__}")
    return ok
