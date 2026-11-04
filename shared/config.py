import os
from contextvars import ContextVar
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from shared.errors import ConfigError


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Member(StrictModel):
    name: str = Field(min_length=1)
    github: str = Field(min_length=1)
    lark: str = Field(min_length=1)


class GitHub(StrictModel):
    enabled: bool = False
    repos: list[str] = Field(default_factory=list)
    token_env: str = "GITHUB_TOKEN"


class Lark(StrictModel):
    app_id_env: str = "LARK_APP_ID"
    app_secret_env: str = "LARK_APP_SECRET"
    tasks_enabled: bool = False
    task_mode: Literal["tasklist", "events"] = "tasklist"
    task_events: str = "data/task-events.jsonl"
    project_id: str = ""
    messages_enabled: bool = False
    chat_id: str = ""
    chat_name: str = "项目协作群"
    keywords: list[str] = Field(default_factory=list)
    sensitive_keywords: list[str] = Field(default_factory=lambda: ["薪资", "绩效", "裁员"])


class Email(StrictModel):
    enabled: bool = False
    host: str = ""
    port: int = Field(default=465, ge=1, le=65535)
    security: Literal["ssl", "starttls", "plain"] = "ssl"
    username_env: str = "SMTP_USERNAME"
    password_env: str = "SMTP_PASSWORD"
    sender: str = ""
    recipients: list[str] = Field(default_factory=list)


class Bot(StrictModel):
    enabled: bool = False
    webhook_env: str = "LARK_BOT_WEBHOOK"
    signing_secret_env: str = "LARK_BOT_SECRET"
    chat_id: str = ""


class HTTP(StrictModel):
    timeout: float = Field(default=8, gt=0, le=30)
    retries: int = Field(default=3, ge=0, le=3)
    retry_interval: float = Field(default=5, ge=0, le=5)
    max_rate_wait: float = Field(default=10, ge=0, le=30)
    source_deadline: float = Field(default=45, gt=0, le=50)


class Settings(StrictModel):
    team_name: str = Field(min_length=1)
    members: list[Member] = Field(min_length=1)
    timezone: str = "Asia/Shanghai"
    calendar: Literal["CN", "weekdays"] = "CN"
    window: Literal["today", "rolling24h"] = "today"
    database: str = "data/daily.sqlite3"
    output_dir: str = "output"
    github: GitHub = Field(default_factory=GitHub)
    lark: Lark = Field(default_factory=Lark)
    email: Email = Field(default_factory=Email)
    bot: Bot = Field(default_factory=Bot)
    http: HTTP = Field(default_factory=HTTP)

    @model_validator(mode="after")
    def validate_setup(self) -> "Settings":
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone 不是有效时区") from exc
        for key in ("name", "github", "lark"):
            values = [getattr(m, key).casefold() for m in self.members]
            if len(values) != len(set(values)):
                raise ValueError(f"members.{key} 必须唯一")
        if self.github.enabled:
            if not self.github.repos or any(
                len(r.split("/")) != 2 or any(not x or x in (".", "..") for x in r.split("/"))
                for r in self.github.repos
            ):
                raise ValueError("github.repos 必须包含 owner/repo")
        if self.lark.messages_enabled and not self.lark.chat_id:
            raise ValueError("lark.chat_id 必填")
        if self.lark.tasks_enabled and not self.lark.project_id:
            raise ValueError("lark.project_id 必填")
        if self.email.enabled and not (
            self.email.host and self.email.sender and self.email.recipients
        ):
            raise ValueError("email 启用时 host/sender/recipients 必填")
        if self.bot.enabled and not self.bot.chat_id:
            raise ValueError("bot.chat_id 必填")
        return self


_current: ContextVar[Settings | None] = ContextVar("daily_settings", default=None)


def configure(settings: Settings) -> None:
    _current.set(settings)


def get_config() -> Settings:
    settings = _current.get()
    if settings is None:
        raise ConfigError("配置尚未加载")
    return settings


def secret(env_name: str, required: bool = True) -> str:
    value = os.environ.get(env_name, "")
    if required and not value:
        raise ConfigError(f"缺少环境变量 {env_name}")
    return value


def load(path: str = "config.yaml") -> Settings:
    try:
        config_path = Path(path).resolve()
        settings = Settings.model_validate(yaml.safe_load(config_path.read_text(encoding="utf-8")))
        # 路径相对于配置文件，避免 cron 工作目录影响结果。
        for name in ("database", "output_dir"):
            setattr(settings, name, str(config_path.parent / getattr(settings, name)))
        settings.lark.task_events = str(config_path.parent / settings.lark.task_events)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        # Pydantic 的原始错误可能包含输入值，不将其写入日志。
        if isinstance(exc, ValidationError):
            detail = "; ".join(
                f"{'.'.join(map(str, e['loc'])) or 'config'}: {e['msg']}"
                for e in exc.errors(include_input=False)
            )
        else:
            detail = "无法读取配置文件或 YAML 格式错误"
        raise ConfigError(detail) from None
    configure(settings)
    return settings
