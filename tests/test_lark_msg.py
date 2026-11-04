import json
from datetime import timedelta

import httpx

from collector.lark_msg import collect


def message(now, text, key="m1"):
    return {
        "message_id": key,
        "msg_type": "text",
        "sender": {"id": "ou_alice"},
        "create_time": str(int(now.timestamp() * 1000)),
        "body": {"content": json.dumps({"text": text})},
    }


def test_refresh_pagination_keywords_and_sensitive_filter(cfg, now, mock_http):
    auth_calls = []
    message_calls = []

    def handler(request):
        if "/auth/" in request.url.path:
            auth_calls.append(request)
            return httpx.Response(
                200, json={"code": 0, "tenant_access_token": f"token{len(auth_calls)}"}
            )
        message_calls.append(request)
        if len(message_calls) == 1:
            return httpx.Response(200, json={"code": 99991663})
        if request.url.params.get("page_token"):
            items = [message(now, "项目完成", "m4"), message(now, "项目完成")]
            return httpx.Response(
                200, json={"code": 0, "data": {"items": items, "has_more": False}}
            )
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "items": [
                        message(now, "项目发布"),
                        message(now, "项目薪资", "m2"),
                        message(now, "午餐", "m3"),
                    ],
                    "has_more": True,
                    "page_token": "next",
                },
            },
        )

    mock_http(handler)
    result = collect("oc_chat", ["项目"], now - timedelta(days=1), now)
    assert [r.content for r in result] == ["项目发布", "项目完成"]
    assert len(auth_calls) == 2 and not result.failed


def test_repeated_expired_token_fails_after_one_refresh(cfg, now, mock_http):
    auth = []

    def handler(request):
        if "/auth/" in request.url.path:
            auth.append(1)
            return httpx.Response(200, json={"code": 0, "tenant_access_token": "token"})
        return httpx.Response(200, json={"code": 99991663})

    mock_http(handler)
    assert collect("oc_chat", ["项目"], now - timedelta(days=1), now).failed
    assert len(auth) == 2
