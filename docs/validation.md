# 本地验证记录

日期：2026-11-04。使用本地虚拟环境；所有自动化外部服务均为 mock。

- `uv sync`：通过；依赖锁定于 uv.lock。
- `pytest -q`：40 passed，含 Task v2 分页、子孙任务去重、多负责人、token 刷新、超时重试、历史快照拒绝和展示语义。
- `ruff check .`、`ruff format --check .`：通过。
- `mypy collector generator notifier shared main.py`：24 个源文件通过。
- 浏览器：375px、768px 无横向溢出；成员筛选与空记录展示、阅读/Markdown 切换、方向键切换通过。
- Markdown 导出：浏览器下载成功，文件内容与生成的 `.md` 完全一致。
- 复制：页面提示成功，但当前浏览器连接的剪贴板读取为空；未将其记为端到端通过，需在用户浏览器复核。
- 双轴独立复核：需求侧发现事件显示字段误去重，可靠性侧发现 SMTP 部分拒收重复发送、STARTTLS 连接清理和 HTTP 慢流预算问题；已修正并补回归测试。HTTP 为请求/数据块间协作截止，不能作为进程级硬截止。
- Docker：检测到 CLI，但 Linux Engine 未运行，构建和容器运行未验证。
- 真实 GitHub、飞书、SMTP、服务器定时任务：未提供授权，未验证、未发送。

剩余范围见 [实施进度](implementation-status.md)，运行方式见 [运维文档](operations.md)。
