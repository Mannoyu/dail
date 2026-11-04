from generator.formatter import generate, refresh
from generator.template import email_html
from shared.models import CommitRecord, MemberReport, SourceStatus


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
