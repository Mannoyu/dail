import smtplib
import ssl
import time
from email.message import EmailMessage

from shared.config import get_config, secret
from shared.logger import get_logger
from shared.models import DailyReport


def connect() -> smtplib.SMTP:
    cfg = get_config().email
    client: smtplib.SMTP
    if cfg.security == "ssl":
        client = smtplib.SMTP_SSL(
            cfg.host, cfg.port, timeout=8, context=ssl.create_default_context()
        )
    else:
        client = smtplib.SMTP(cfg.host, cfg.port, timeout=8)
    try:
        if cfg.security == "starttls":
            client.starttls(context=ssl.create_default_context())
        username = secret(cfg.username_env, required=False)
        if username:
            client.login(username, secret(cfg.password_env))
    except Exception:
        client.close()
        raise
    return client


def send(report: DailyReport, recipients: list[str]) -> bool:
    cfg = get_config().email
    if not recipients:
        return False
    try:
        message = EmailMessage()
        message["Subject"] = f"{report.team_name} · {report.date} 工作日报"
        message["From"] = cfg.sender
        message["To"] = ", ".join(recipients)
        message.set_content(report.markdown)
        # Email body is a static, script-free rendering, not the interactive reader.
        from generator.template import email_html

        message.add_alternative(email_html(report), subtype="html")
    except Exception:
        get_logger(__name__).error("邮件构造失败")
        return False
    pending = list(dict.fromkeys(recipients))
    for attempt in range(3):
        try:
            with connect() as client:
                try:
                    refused = client.send_message(message, to_addrs=pending)
                except smtplib.SMTPRecipientsRefused as exc:
                    refused = exc.recipients
                # SMTP has accepted every address absent from the refusal mapping.
                # Do not resend to those addresses when retrying partial delivery.
                pending = [address for address in pending if address in refused]
            if not pending:
                return True
            get_logger(__name__).error(f"邮件部分拒收 attempt={attempt + 1} count={len(pending)}")
        except Exception:
            get_logger(__name__).error(f"邮件推送失败 attempt={attempt + 1}")
        if attempt < 2 and pending:
            time.sleep(1)
        if not pending:
            return True
    return False
