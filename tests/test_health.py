from unittest.mock import MagicMock

from shared.health import check


def test_health_never_delivers_or_creates_output(cfg, mock_http, monkeypatch):
    import httpx

    cfg.lark.tasks_enabled = False
    cfg.bot.enabled = True
    monkeypatch.setenv("LARK_BOT_WEBHOOK", "https://open.feishu.cn/open-apis/bot/v2/test")
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("tenant_access_token/internal"):
            return httpx.Response(200, json={"code": 0, "tenant_access_token": "test"})
        if request.url.path.endswith("/messages"):
            return httpx.Response(200, json={"code": 0, "data": {"items": []}})
        return httpx.Response(200, json=[])

    sender = MagicMock(side_effect=AssertionError("must not send"))
    monkeypatch.setattr("notifier.email.send", sender)
    monkeypatch.setattr("notifier.lark_bot.send", sender)
    mock_http(handler)
    assert check(cfg)
    sender.assert_not_called()
    assert not any("/bot/" in request.url.path for request in requests)
    from pathlib import Path

    assert not Path(cfg.database).exists() and not Path(cfg.output_dir).exists()
