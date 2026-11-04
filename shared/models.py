from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class CommitRecord:
    author: str
    message: str
    timestamp: datetime
    repo: str
    additions: int
    deletions: int
    files_changed: int


@dataclass(frozen=True)
class TaskRecord:
    assignee: str
    title: str
    status_from: str
    status_to: str
    updated_at: datetime


@dataclass(frozen=True)
class MessageRecord:
    sender: str
    content: str
    timestamp: datetime
    chat_name: str


@dataclass
class MemberReport:
    name: str
    github_username: str
    commits: list[CommitRecord] = field(default_factory=list)
    tasks: list[TaskRecord] = field(default_factory=list)
    messages: list[MessageRecord] = field(default_factory=list)


@dataclass(frozen=True)
class SourceStatus:
    name: str
    state: str  # ok / failed / disabled
    count: int = 0


@dataclass
class DailyReport:
    date: date
    team_name: str
    members: list[MemberReport]
    markdown: str = ""
    html: str = ""
    sources: list[SourceStatus] = field(default_factory=list)
    demo: bool = False
