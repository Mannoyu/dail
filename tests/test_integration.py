import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from collector.common import Collection
from main import main
from shared.errors import NotifierError
from shared.models import CommitRecord, MessageRecord, TaskRecord
from shared.pipeline import run
from shared.storage import Storage


def sources(monkeypatch, now, fail=()):
    values = {
        "github": [CommitRecord("alice", "test", now, "org/repo", 5, 2, 1)],
        "lark_task": [TaskRecord("ou_alice", "task", "todo", "done", now)],
        "lark_msg": [MessageRecord("ou_alice", "项目", now, "team")],
    }
    for name, records in values.items():
        result = Collection(records if name not in fail else [], failed=name in fail)
        monkeypatch.setattr(f"shared.pipeline.{name}.collect", lambda *_, r=result: r)


def test_full_run_saves_sends_and_handles_empty_member(cfg, now, monkeypatch):
    sources(monkeypatch, now)
    cfg.email.enabled = cfg.bot.enabled = True
    sends = [MagicMock(return_value=True), MagicMock(return_value=True)]
    monkeypatch.setattr("shared.pipeline.email.send", sends[0])
    monkeypatch.setattr("shared.pipeline.lark_bot.send", sends[1])
    started = time.monotonic()
    report = run(cfg, now)
    assert time.monotonic() - started < 60
    assert "当日无记录" in report.markdown
    assert Storage(cfg.database).get(str(now.date()), cfg.team_name) is not None
    assert (Path(cfg.output_dir) / f"{now.date()}.html").exists()
    assert all(mock.call_count == 1 for mock in sends)


def test_degraded_source_is_visible(cfg, now, monkeypatch):
    sources(monkeypatch, now, ("github",))
    report = run(cfg, now, dry_run=True)
    assert "数据获取失败" in report.markdown
    assert len(report.members[0].tasks) == 1


def test_all_failed_creates_no_report(cfg, now, monkeypatch):
    sources(monkeypatch, now, ("github", "lark_task", "lark_msg"))
    assert run(cfg, now) is None
    assert not Path(cfg.database).exists() and not Path(cfg.output_dir).exists()


def test_dry_run_never_sends(cfg, now, monkeypatch):
    sources(monkeypatch, now)
    cfg.email.enabled = cfg.bot.enabled = True
    sender = MagicMock(side_effect=AssertionError("must not send"))
    monkeypatch.setattr("shared.pipeline.email.send", sender)
    monkeypatch.setattr("shared.pipeline.lark_bot.send", sender)
    assert run(cfg, now, dry_run=True) is not None
    sender.assert_not_called()


def test_delivery_failure_uses_both_channels_and_nonzero(cfg, now, monkeypatch):
    sources(monkeypatch, now)
    cfg.email.enabled = cfg.bot.enabled = True
    monkeypatch.setattr("shared.pipeline.email.send", lambda *_: False)
    fallback = MagicMock(return_value=True)
    monkeypatch.setattr("shared.pipeline.lark_bot.send", fallback)
    with pytest.raises(NotifierError):
        run(cfg, now)
    fallback.assert_called_once()


def test_cli_demo_no_config_and_no_credentials(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert main(["--demo", "--output", str(tmp_path), "--date", "2026-11-04"]) == 0
    assert (tmp_path / "2026-11-04-demo.html").exists()


def test_cli_holiday_skip(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    path.write_text("team_name: test\nmembers: [{name: a, github: a, lark: a}]", encoding="utf-8")
    runner = MagicMock(side_effect=AssertionError("must skip"))
    monkeypatch.setattr("main.run", runner)
    assert main(["--config", str(path), "--date", "2026-10-01"]) == 0
    runner.assert_not_called()
