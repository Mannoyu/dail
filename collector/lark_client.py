from typing import Any

from shared.config import get_config, secret
from shared.errors import CollectorError
from shared.http import APIClient

BASE = "https://open.feishu.cn/open-apis"
EXPIRED_CODES = {99991661, 99991663, 99991668}


class LarkClient:
    def __init__(self, api: APIClient):
        self.api = api
        self.token = ""

    def refresh(self) -> None:
        cfg = get_config().lark
        result = self.api.request(
            "POST",
            BASE + "/auth/v3/tenant_access_token/internal",
            json={
                "app_id": secret(cfg.app_id_env),
                "app_secret": secret(cfg.app_secret_env),
            },
        )
        if result.get("code") != 0 or not result.get("tenant_access_token"):
            raise CollectorError("飞书授权失败")
        self.token = result["tenant_access_token"]

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.token:
            self.refresh()
        for attempt in range(2):
            result = self.api.request(
                "GET", BASE + path, params=params, headers={"Authorization": f"Bearer {self.token}"}
            )
            if result.get("code") in EXPIRED_CODES and attempt == 0:
                self.refresh()
                continue
            if result.get("code") != 0:
                raise CollectorError("飞书业务接口失败")
            return result["data"]
        raise CollectorError("飞书 token 刷新失败")
