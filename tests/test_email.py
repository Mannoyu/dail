import smtplib
from unittest.mock import MagicMock

from notifier.email import connect, send
from shared.demo import build


def test_multipart_email_subject_and_html(cfg, now, monkeypatch):
    cfg.email.sender = "daily@example.com"
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    smtp.send_message.return_value = {}
    monkeypatch.setattr("notifier.email.connect", lambda: smtp)
    assert send(build(now), ["leader@example.com"])
    mail = smtp.send_message.call_args.args[0]
    assert "产品研发组" in mail["Subject"] and str(now.date()) in mail["Subject"]
    assert mail.get_body(preferencelist=("html",)).get_content_type() == "text/html"
    assert "<script" not in mail.get_body(preferencelist=("html",)).get_content()


def test_retry_exhaustion(cfg, now, monkeypatch):
    calls = []

    def fail():
        calls.append(1)
        raise smtplib.SMTPException("failed")

    monkeypatch.setattr("notifier.email.connect", fail)
    monkeypatch.setattr("notifier.email.time.sleep", lambda _: None)
    assert not send(build(now), ["leader@example.com"])
    assert len(calls) == 3


def test_partial_refusal_retries_only_rejected_recipient(cfg, now, monkeypatch):
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    smtp.send_message.side_effect = [{"bad@example.com": (450, b"later")}, {}]
    monkeypatch.setattr("notifier.email.connect", lambda: smtp)
    monkeypatch.setattr("notifier.email.time.sleep", lambda _: None)
    assert send(build(now), ["good@example.com", "bad@example.com"])
    assert [call.kwargs["to_addrs"] for call in smtp.send_message.call_args_list] == [
        ["good@example.com", "bad@example.com"],
        ["bad@example.com"],
    ]


def test_starttls_failure_closes_connection(cfg, monkeypatch):
    import pytest

    cfg.email.security = "starttls"
    smtp = MagicMock()
    smtp.starttls.side_effect = smtplib.SMTPException("TLS failed")
    monkeypatch.setattr("notifier.email.smtplib.SMTP", lambda *a, **k: smtp)
    with pytest.raises(smtplib.SMTPException):
        connect()
    smtp.close.assert_called_once()
