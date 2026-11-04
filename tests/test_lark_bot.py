import json

import httpx

from notifier.lark_bot import send
from shared.demo import build


def test_card_contains_markdown_and_signature(cfg, now, mock_http, monkeypatch):
    cfg.bot.chat_id = "oc_chat"
    monkeypatch.setenv("LARK_BOT_WEBHOOK", "https://open.feishu.cn/open-apis/bot/v2/hook/test")
    monkeypatch.setenv("LARK_BOT_SECRET", "secret")
    payloads = []

    def handler(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={"code": 0})

    mock_http(handler)
    assert send(build(now), "oc_chat")
    assert payloads[0]["card"]["elements"][0]["tag"] == "markdown"
    assert "sign" in payloads[0]


def test_business_error_retries_and_never_claims_success(cfg, now, mock_http, monkeypatch):
    cfg.bot.chat_id = "oc_chat"
    monkeypatch.setenv("LARK_BOT_WEBHOOK", "https://example.com/hook")
    monkeypatch.setattr("notifier.lark_bot.time.sleep", lambda _: None)
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"code": 19001})

    mock_http(handler)
    assert not send(build(now), "oc_chat") and len(calls) == 3
