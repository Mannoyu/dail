from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from shared.config import Settings, configure


@pytest.fixture
def now():
    return datetime(2026, 11, 4, 18, tzinfo=ZoneInfo("Asia/Shanghai"))


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    settings = Settings.model_validate(
        {
            "team_name": "研发组",
            "members": [
                {"name": "张三", "github": "alice", "lark": "ou_alice"},
                {"name": "李四", "github": "bob", "lark": "ou_bob"},
            ],
            "github": {"enabled": True, "repos": ["org/repo"]},
            "lark": {
                "tasks_enabled": True,
                "task_mode": "events",
                "project_id": "project",
                "task_events": str(tmp_path / "events.jsonl"),
                "messages_enabled": True,
                "chat_id": "oc_chat",
                "keywords": ["项目"],
            },
            "database": str(tmp_path / "daily.sqlite3"),
            "output_dir": str(tmp_path / "output"),
            "http": {"retry_interval": 0},
        }
    )
    for key in ["GITHUB_TOKEN", "LARK_APP_ID", "LARK_APP_SECRET", "LARK_BOT_WEBHOOK"]:
        monkeypatch.setenv(key, "test-only")
    configure(settings)
    return settings


@pytest.fixture
def mock_http(monkeypatch):
    real_client = httpx.Client

    def install(handler):
        def factory(**kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            return real_client(**kwargs)

        monkeypatch.setattr(httpx, "Client", factory)

    return install
