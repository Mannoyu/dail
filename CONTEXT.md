# Daily Brief 项目上下文

需求真源：`specs/proposal.md`；架构真源：`specs/design.md`；原始任务：`specs/task.md`。

面向 5–15 人研发团队，以配置白名单采集 GitHub 提交、任务状态事件、飞书项目消息，按账号映射生成三段式成员日报。禁止 AI 总结、代码 diff、敏感消息、手动编辑及历史统计产品功能。

执行路线采用 ask-matt 的已有规格 → 可验收切片 → 实现 → 复核流程。已有 SDD 代替重复访谈和重写 PRD。无远程仓库关联，工作项暂记录在 `docs/implementation-status.md`，不在用户提供的参考仓库创建 issue。未改写用户原始规范。

术语：TaskRecord 是任务流转记录；MessageRecord 是群消息记录。Collection 是 list 子类，附带 failed 标记，区分“无记录”和“采集失败”。

实现决策见 `docs/adr/001-implementation.md`。真实外部服务、任务事件上游、Docker 和服务器调度仍须独立联调；mock 成功不代表线上验收通过。
