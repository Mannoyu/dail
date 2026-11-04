# 本地运行与部署

## 运行

```bash
uv sync --locked
uv run python main.py --demo
# 浏览器直接打开 output/<日期>-demo.html，或仅服务输出目录：
uv run python -m http.server 8765 --bind 127.0.0.1 --directory output
```

演示无需配置、密钥或网络，不写入真实日报数据库，也不会推送。页面支持成员筛选、阅读/Markdown 切换、复制和完整团队 Markdown 下载。成员筛选只影响阅读视图；统计与导出保留全团队。

复制 `config.yaml.example` 为 `config.yaml`，填入白名单和账号映射，并在运行环境设置所引用的环境变量。应用不自动读取 `.env`。所有文件路径相对于配置文件。

```bash
uv run python main.py --check
uv run python main.py --dry-run
uv run python main.py --date 2026-11-04 --dry-run
uv run python main.py --force --dry-run
# 真正推送：仅在配置启用渠道并核对收件人后执行
uv run python main.py
```

`--check` 对 GitHub 提交读取、飞书消息权限、事件文件可读性和 SMTP 登录执行只读检查。机器人 webhook 仅检查配置格式，**不会试发消息，也不声称验证实际送达**。没有启用数据源时健康检查失败。检查模式不检查当日工作日限制。

真实执行支持当日窗口和 rolling24h。未关联 GitHub 登录身份的提交不会按姓名误归属；请核对日志中的 unmapped_records。

## 任务状态事件接入（待线上适配）

普通任务当前状态不等于状态流转历史。需要使用实际飞书项目的授权接口，或由可信上游将精确变更事件写入 `lark.task_events` JSON Lines 文件。**首版尚不提供飞书项目原生 API 或 webhook 接收器。** 每行：

```json
{"event_id":"unique-event-1","project_id":"your-project","assignee":"ou_replace_with_open_id","title":"接口联调","status_from":"进行中","status_to":"已完成","updated_at":"2026-11-04T16:30:00+08:00"}
```

空文件表示无事件，文件缺失/格式错误表示获取失败。归档必须由上游按需滚动更新；CLI 不会自动同步它。

建议上游提供稳定且唯一的 `event_id`，采集器只按该标识去重；未提供时保留每条记录，不用标题、负责人和时间猜测是否同一任务。

## 容器与调度

```bash
docker build -t daily-brief .
docker run --rm daily-brief --demo --output /tmp/demo
docker run --rm --env-file /secure/daily.env \
  -v /srv/daily/config.yaml:/app/config.yaml:ro \
  -v /srv/daily/data:/app/data \
  -v /srv/daily/output:/app/output daily-brief --dry-run
```

Docker 命令为部署示例，当前未在 Docker 环境实测。定时示例见 `deploy/daily.cron.example`，服务器时区应设为 Asia/Shanghai。每天 18:00 触发，应用跳过假日并识别调休工作日；使用 flock 防止同一进程重叠。提前创建 data、output、logs，按服务器账号配置读取权限。

SQLite 同日期/团队重复生成会覆盖日报；重复真实执行会重复推送，因此不要在未确认前重试发送。发送失败会返回非零，已成功的渠道不撤回。请为 Cron 非零退出和 ERROR 日志配置现有运维告警。当前重试与预算可导致大型仓库降级，不保证所有规模均在 60 秒内完成。

## 开发验证

HTTP 在每个请求与响应数据块之间检查源预算；阻塞的单次 socket 阶段仍可能超出剩余预算，受该阶段 timeout 限制。这不是进程级硬截止。调度器可另设总运行时限。

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy collector generator notifier shared main.py
```

真实联调需要单独验证授权、任务历史完整性、SMTP/机器人到达情况及五人团队 <60s。所有本机自动化测试均使用 mock，不发送邮件或群消息。
