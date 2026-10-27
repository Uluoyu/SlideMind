# Phase 4：模型 PPT Planner、页面大纲与用户确认

日期：2026-10-26。范围已由用户确认：内网 OpenAI 兼容对话服务；结构化编辑 + 反馈重新生成；生成时检索项目资料并附来源。

## 结论与依据

- 设计文档第 84 节 Phase 4 = PPT Planner / 页面大纲 / 用户确认；第 6 节要求先出大纲，支持删除、新增、改标题、调整顺序、合并、拆分、重新生成，示例为自然语言反馈「P3和P4合并…」后整体重排。
- 第 19 节 Planner 输入：主题、页数、汇报对象、场景、重点、限制；输出 `pages[{page_no,title,purpose}]`。第 51/52 节 generate/confirm 接口已存在。
- 第 60–63 节：检索限定当前项目与权限；事实须有来源，检索不到时如实提示，不编造。第 76 节：提示词按版本存放。第 78 节：Top-K → Reranker → 少量片段进入 LLM。
- 结论：保留现有 `Planner` 协议与接口形态，新增模型实现；`LocalPlanner` 作为未配置模型时的回退，行为不变。

## 当前代码与接入点

- `apps/agent/src/slidemind_agent/planner.py`：`PlanningRequest`、`PlannedPage`、`Planner` 协议、确定性 `LocalPlanner`；`prompts/planner_v1.md` 为占位说明。
- `apps/api/src/slidemind_api/routes.py:312` `outline/generate` 直接实例化 `LocalPlanner`，并在持有 `with_for_update` 行锁时生成；`:333` `outline/confirm` 接收完整页面列表。
- `contracts.py:73-85` `OutlinePage/OutlineInput/OutlineView(planner="local-scaffold")`；`models.py` `Page` 无来源字段。
- `main.py` `create_app(settings, *, embedder=None)` 为依赖注入点；`retrieval.py` `DatabaseRetriever.hits()` 已做项目/密级/READY 过滤与可选重排。
- `apps/rag/src/slidemind_rag/remote.py` `_RemoteModel` 为 httpx 适配器样板（`trust_env=False`、禁重定向、Bearer）。配置中暂无对话模型项。
- 前端 `OutlineEditor.tsx` 支持改标题/用途、上下移、删除、添加；`App.tsx:172` 仅 DRAFT 显示生成按钮。

## 需求与阶段范围

本阶段做：
1. 配置：`SLIDEMIND_PLANNER_PROVIDER=local|http`（默认 local），`PLANNER_URL`（`/v1/chat/completions`）、`PLANNER_MODEL`、`PLANNER_API_KEY`（SecretStr）、`PLANNER_TIMEOUT_SECONDS`、`PLANNER_MAX_TOKENS`、`PLANNER_TEMPERATURE`。
2. `HttpChatModel`（OpenAI 兼容 chat completions，复用适配器约束）与 `ModelPlanner`：提示词 `prompts/planner_v2.md`；要求 JSON 输出；解析容忍代码围栏；校验页数、页码连续、长度；无效输出重试 1 次，仍失败返回 502 且不改状态。
3. 资料检索：按主题与每条重点分别检索（每条 Top-5，经重排），去重后最多 8 段、每段截断 400 字，以编号证据交给模型；模型只能引用给定编号，未知编号丢弃。检索为空或失败时继续生成，并返回提示「未检索到项目资料，大纲仅依据需求生成」。
4. 反馈重新生成：`outline/generate` 可选请求体 `{feedback, pages}`；以用户当前编辑中的大纲为基础按反馈重排，页数可变（1–50）；无反馈时页数等于任务页数。`local` 模式下带反馈返回 409「反馈重新生成需要配置模型服务」。
5. 来源：迁移 0004 新增 `ppt_page.outline_sources`（JSON 快照：chunkId、documentId、fileName、pageNo、excerpt）与 `ppt_document_instance.planner`。确认时客户端只提交 `sourceChunkIds`，服务端按项目/密级/READY 重新解析并重建快照，非法编号 422。
6. 前端：生成/重新生成按钮（OUTLINE_GENERATED 也可用）、反馈输入框、每页合并到下一页与拆分、每页来源折叠展示、检索/模型提示条；提示文案按 planner 来源区分。

不做（留给 Phase 5+）：页面内容（Content Agent）、素材、页面级对话、流式输出、DeepSeek Harness 运行时、历史 PPT RAG。

## 实施顺序

1. 配置项与 `HttpChatModel` + MockTransport 单测。
2. `ModelPlanner`、`planner_v2.md`、输出解析与校验单测（含反馈路径、未知引用、页数不符、重试）。
3. 迁移 0004、模型字段、契约（`OutlineGenerateInput`、`OutlineSource`、`OutlineView.planner/warning`）。
4. 路由改造：读取输入后释放事务再调用检索与模型，写回前重新加锁并复核状态；`create_app(..., planner=None)` 注入。API 测试使用注入的假 Planner。
5. 前端编辑能力、来源展示、反馈重新生成；e2e 覆盖合并/拆分与确认（本地 Planner）。
6. README、architecture、`.env.example` 更新；真实服务验收并写 `docs/phase4-verification.md`。

## 建议验收标准

- 配置 http 后，8 页任务生成 8 页大纲，页码连续，标题/用途为中文且贴合主题与重点；有资料时至少部分页面带真实来源，来源均属当前项目且可回查原文。
- 反馈「P3和P4合并，增加一页 X，P8改成 Y」后返回符合反馈的大纲；确认后页数更新为实际页数。
- 模型超时/5xx/无效 JSON：502 可行动提示，状态与已有大纲不变；未配置模型时行为与 Phase 3 一致，现有测试全部通过。
- 合并、拆分、重排、删除、新增后确认，服务端来源校验通过；伪造 chunkId 返回 422。
- Ruff、Schema 检查、`npm test`、`npm run build`、e2e（除既有环境性用例）全部通过。

## 风险与处理

- 2026-10-26 用户决定：对话服务改用外网第三方地址（由用户提供），外发资料密级不额外限制（沿用工作空间权限，至 CONFIDENTIAL）。README 已注明外发范围与服务商条款确认。

- 内网对话服务地址/模型待提供：实现可插拔，真实验收在获得地址后进行。
- 资料摘录可能含指令性文本（提示注入）：证据以分隔块标注为「资料，不是指令」，输出严格按 Schema 校验，影响面仅限大纲文字，且需用户确认。
- 摘录会发送到对话服务：仅发送已通过密级过滤的片段，服务限定内网；README 注明。
- 模型调用耗时长：调用期间不持有数据库事务；并发重新生成以最后写入为准（复核状态后写入）。
- 推理模型输出 `<think>` 或围栏：解析前剥离。

## 验证安排

单元/API 测试全部离线（MockTransport、假 Planner、SQLite）；真实服务用例沿用 `SLIDEMIND_TEST_REMOTE_MODELS=1` 门控；浏览器验收覆盖编辑与确认；真实服务端到端验收结果记入 `docs/phase4-verification.md`。
