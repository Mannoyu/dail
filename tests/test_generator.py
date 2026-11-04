from generator.formatter import generate, refresh
from generator.template import email_html
from shared.models import CommitRecord, MemberReport, SourceStatus, TaskRecord


def test_sections_empty_and_external_text_escaped(now):
    attack = '</script><img src=x onerror="alert(1)"> [x](javascript:alert(1))'
    member = MemberReport(
        "张三", "alice", [CommitRecord("alice", attack, now, "org/repo", 1, 2, 1)]
    )
    report = generate([member, MemberReport("李四", "bob")], now.date(), "研发")
    assert all(s in report.markdown for s in ["代码提交", "任务进展", "协作沟通", "当日无记录"])
    assert "<img src=x" not in report.html
    assert "<img src=x" not in email_html(report)
    assert 'href="javascript:' not in email_html(report)
    assert "application/json" in report.html and "&lt;/script&gt;" in report.html


def test_failed_source_marked_for_every_member(now):
    report = generate([MemberReport("甲", "a"), MemberReport("乙", "b")], now.date(), "团队")
    report.sources = [SourceStatus("github", "failed")]
    refresh(report)
    assert report.markdown.count("数据获取失败") == 2
    assert report.html.count("请检查数据源连接") == 2


def test_snapshot_has_current_state_without_invented_transition(now):
    report = generate(
        [MemberReport("甲", "a", tasks=[TaskRecord("ou_a", "任务", "", "进行中", now)])],
        now.date(),
        "团队",
    )
    report.task_mode = "tasklist"
    refresh(report)
    assert "当前状态：进行中" in report.markdown
    assert "→" not in report.markdown
    assert "项任务快照" in report.html and "不代表状态流转历史" in report.html
