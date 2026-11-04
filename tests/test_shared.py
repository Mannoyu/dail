import json
import logging

import pytest

from shared.calendar import is_workday
from shared.config import load
from shared.errors import ConfigError
from shared.logger import JSONFormatter
from shared.models import DailyReport
from shared.storage import Storage


def test_config_relative_paths_and_missing_fields(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "team_name: test\nmembers: [{name: A, github: a, lark: ou_a}]", encoding="utf-8"
    )
    cfg = load(str(path))
    assert cfg.database == str(tmp_path / "data/daily.sqlite3")
    path.write_text("team_name: test", encoding="utf-8")
    with pytest.raises(ConfigError, match="members"):
        load(str(path))


def test_config_errors_do_not_disclose_input(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("team_name: test\napi_password: TOP_SECRET", encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        load(str(path))
    assert "TOP_SECRET" not in str(exc.value)


def test_json_logger():
    record = logging.LogRecord("test", logging.INFO, "", 1, "中文日志", (), None)
    data = json.loads(JSONFormatter().format(record))
    assert data["level"] == "INFO" and data["event"] == "中文日志"


def test_storage_upsert(tmp_path, now):
    db = Storage(str(tmp_path / "nested/test.db"))
    report = DailyReport(now.date(), "团队", [], "first", "<p>first</p>")
    db.save(report)
    report.markdown = "updated"
    db.save(report)
    assert db.get(str(now.date()), "团队")["markdown"] == "updated"
    assert db.get("2000-01-01", "团队") is None


def test_calendar_holiday_makeup_day():
    from datetime import date

    assert not is_workday(date(2026, 10, 1), "CN")
    assert is_workday(date(2026, 10, 10), "CN")  # Saturday makeup workday
    assert not is_workday(date(2026, 10, 10), "weekdays")
