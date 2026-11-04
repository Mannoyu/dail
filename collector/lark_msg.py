import json
from datetime import UTC, datetime

from collector.common import check_window, guarded
from collector.lark_client import LarkClient
from shared.config import get_config
from shared.errors import CollectorError
from shared.http import APIClient
from shared.models import MessageRecord


@guarded
def collect(
    chat_id: str, keywords: list[str], since: datetime, until: datetime
) -> list[MessageRecord]:
    check_window(since, until)
    cfg = get_config().lark
    if chat_id != cfg.chat_id:
        raise CollectorError("群组不在配置白名单内")
    records = []
    seen: set[str] = set()
    tokens: set[str] = set()
    with APIClient() as api:
        lark = LarkClient(api)
        params = {
            "container_id_type": "chat",
            "container_id": chat_id,
            "start_time": str(int(since.timestamp())),
            "end_time": str(int(until.timestamp())),
            "page_size": 50,
            "sort_type": "ByCreateTimeAsc",
        }
        while True:
            data = lark.get("/im/v1/messages", params)
            for item in data.get("items", []):
                if item.get("deleted") or item.get("msg_type") != "text":
                    continue
                key = item["message_id"]
                if key in seen:
                    continue
                seen.add(key)
                content = json.loads(item["body"]["content"]).get("text", "")
                text = content.casefold()
                if any(word.casefold() in text for word in cfg.sensitive_keywords):
                    continue
                if not keywords or not any(word.casefold() in text for word in keywords):
                    continue
                timestamp = datetime.fromtimestamp(int(item["create_time"]) / 1000, UTC)
                if since <= timestamp <= until:
                    records.append(
                        MessageRecord(item["sender"]["id"], content, timestamp, cfg.chat_name)
                    )
            if not data.get("has_more"):
                break
            token = data.get("page_token")
            if not token or token in tokens:
                raise CollectorError("飞书分页游标未前进")
            tokens.add(token)
            params["page_token"] = token
    return records
