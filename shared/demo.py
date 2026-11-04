from datetime import datetime

from generator.formatter import refresh
from shared.models import (
    CommitRecord,
    DailyReport,
    MemberReport,
    MessageRecord,
    SourceStatus,
    TaskRecord,
)


def build(now: datetime) -> DailyReport:
    members = [
        MemberReport(
            "林知远",
            "zhiyuan-lin",
            [
                CommitRecord(
                    "zhiyuan-lin",
                    "feat: 完成日报采集管道，支持多数据源并发归集",
                    now,
                    "daily-brief/core",
                    186,
                    32,
                    8,
                ),
                CommitRecord(
                    "zhiyuan-lin",
                    "fix: 修复 GitHub 分页采集时的重复记录",
                    now,
                    "daily-brief/core",
                    42,
                    18,
                    3,
                ),
            ],
            [TaskRecord("ou_lin", "日报数据采集模块联调", "进行中", "已完成", now)],
            [
                MessageRecord(
                    "ou_lin",
                    "项目采集接口已完成联调，异常数据源会单独标记，不影响其他来源。",
                    now,
                    "Daily Brief · 产品研发",
                ),
            ],
        ),
        MemberReport(
            "陈雨桐",
            "yutong-chen",
            [
                CommitRecord(
                    "yutong-chen",
                    "feat: 新增团队日报阅读视图与 Markdown 导出",
                    now,
                    "daily-brief/web",
                    245,
                    51,
                    12,
                ),
                CommitRecord(
                    "yutong-chen",
                    "style: 优化窄屏布局与键盘焦点状态",
                    now,
                    "daily-brief/web",
                    68,
                    24,
                    4,
                ),
            ],
            [TaskRecord("ou_chen", "日报阅读页面交互验收", "待处理", "进行中", now)],
            [
                MessageRecord(
                    "ou_chen",
                    "日报项目的阅读页面已更新，成员筛选与导出可一起验收。",
                    now,
                    "Daily Brief · 产品研发",
                ),
            ],
        ),
        MemberReport(
            "周可欣",
            "kexin-zhou",
            [],
            [
                TaskRecord("ou_zhou", "发布前验收清单整理", "进行中", "已完成", now),
            ],
        ),
        MemberReport("许嘉言", "jiayan-xu"),
    ]
    return refresh(
        DailyReport(
            now.date(),
            "产品研发组",
            members,
            sources=[
                SourceStatus("github", "ok", 4),
                SourceStatus("tasks", "ok", 3),
                SourceStatus("messages", "ok", 2),
            ],
            demo=True,
        )
    )
