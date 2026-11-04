import base64
import hashlib
import hmac
import time

import httpx

from shared.config import get_config, secret
from shared.logger import get_logger
from shared.models import DailyReport


def send(report: DailyReport, chat_id: str) -> bool:
    cfg = get_config().bot
    if chat_id != cfg.chat_id:
        return False
    for attempt in range(3):
        try:
            payload: dict = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": f"{report.team_name} · {report.date}",
                        }
                    },
                    "elements": [{"tag": "markdown", "content": report.markdown}],
                },
            }
            signing_secret = secret(cfg.signing_secret_env, required=False)
            if signing_secret:
                timestamp = str(int(time.time()))
                payload["timestamp"] = timestamp
                payload["sign"] = base64.b64encode(
                    hmac.new(
                        f"{timestamp}\n{signing_secret}".encode(),
                        b"",
                        hashlib.sha256,
                    ).digest()
                ).decode()
            with httpx.Client(timeout=8) as client:
                response = client.post(secret(cfg.webhook_env), json=payload)
                response.raise_for_status()
                result = response.json()
                if result.get("code", result.get("StatusCode", -1)) != 0:
                    raise ValueError("飞书机器人业务失败")
            return True
        except Exception:
            get_logger(__name__).error(f"飞书推送失败 attempt={attempt + 1}")
            if attempt < 2:
                time.sleep(1)
    return False
