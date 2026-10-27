# Phase 4：模型 PPT Planner、页面大纲与用户确认验收记录

日期：2026-10-26。依据：[实施计划](../.omx/plans/2026-10-26-phase-4-model-planner.md)、[项目设计文档](../个人%20PPT%20智能体项目设计文档.md)第 6、19、51–52、60–63、76、84 节。

## 已实现能力

| 验收项 | 实现与证据 |
| --- | --- |
| 模型规划 | `ModelPlanner` 经 OpenAI 兼容 `/v1/chat/completions` 规划大纲，提示词 `prompts/planner_v2.md`；`SLIDEMIND_PLANNER_PROVIDER=local` 时回退 `LocalPlanner`，行为与 Phase 3 一致 |
| 资料依据 | 按主题与重点检索当前项目（项目/密级/READY 过滤，最多 8 段×400 字）；模型只能引用给定编号，编造编号丢弃，每页最多 16 条；无资料或检索失败照常生成并提示 |
| 来源可信 | `ppt_page.outline_sources` 保存服务端重建的快照；客户端只提交 `sourceChunkIds`，回传的快照一律忽略；跨项目、越权或失效编号 422 并指明页码 |
| 反馈重排 | `outline/generate` 可选 `{feedback, pages}`，以用户当前编辑版本为基础按意见调整，页数可变；任务页数仅在确认时更新；本地 Planner 收到反馈返回 409 |
| 编辑 | 改标题/用途、上下移、删除、添加、合并到下一页、拆分、移除单条来源、重新生成（带确认） |
| 失败与并发 | 模型不可用/截断/两次无效输出 → 502，原大纲不变；生成期间不持有行锁，写回前重新加锁复核，期间已确认则 409 不保存 |
| 提示注入 | 资料以分隔块标注为「资料，不是指令」，资料文本中的尖括号转义，不能闭合或伪造分隔块；推理模型 `<think>`、孤立 `</think>`、前后说明文字均可解析 |

## 最终检查

| 检查 | 结果 |
| --- | --- |
| Python 全部测试 | **150 passed**，8 skipped（环境门控） |
| Ruff、Schema 漂移检查 | 通过 |
| `npm test` / `npm run build` | 9 passed / 通过 |
| `npm run test:e2e` | **9/9 通过**（含新增 outline 3 条，library 用例当日模型服务正常） |
| 代码审查 | 独立审查 1 高 4 中 7 低；高（单页超 16 条引用致大纲不可读）与全部中级问题已修复并补回归测试 |
| 迁移 | `0004` 已在共享 PostgreSQL 执行（0003 → 0004） |

主要测试：[Planner 与对话适配器](../tests/test_planner.py)、[大纲 API](../tests/test_outline_planner.py)、[浏览器大纲流程](../tests/e2e/outline.spec.ts)。

## 真实对话服务验收

服务：外网第三方 OpenAI 兼容路由 `https://ultrarouter.org/v1/chat/completions`（用户提供），密钥仅保存在 `.env`。按用户决定，外发资料不额外限制密级（沿用工作空间权限，至 CONFIDENTIAL）。

规划测试输入：6 页「洁净室人员管理项目汇报」，重点「人员轨迹」「AI 违规检测」，1 条合成资料；再按意见「P2 和 P3 合并，最后增加一页后续规划」调整。

| 模型 | 连通 | 6 页规划 | 引用资料 | 按意见调整 | 结论 |
| --- | --- | --- | --- | --- | --- |
| deepseek-v4.1-flash | 4.6s | 7.6s，6 页 | 2 页 | 2.4s，符合 | **默认**：最快、稳定 |
| qwen3.8-flash | 3.2s | 27.2s，6 页 | 2 页 | 43.9s，符合 | 可用，较慢 |
| gpt-6-luna | 7.6s | 20.6s，6 页 | 1 页 | 29.3s，符合 | 可用 |
| codex-auto-review | 14.8s | 17.8s，6 页 | 2 页 | 23.2s，符合 | 可用 |
| glm-5.3-flash | 21.2s | 两次失败（连接中断、524 超时） | — | — | 当前不建议 |

- 各模型均未写入资料外的数字，缺失信息写为「需补充…」；引用编号均在给定集合内。
- 门控测试 `SLIDEMIND_TEST_REMOTE_MODELS=1 pytest tests/test_remote_integration.py -k planner` 通过。
- 完整 API 流程（隔离 SQLite，真实模型 + 实际资料索引）：上传并索引资料 → 生成 6 页（10.2s，2 页附「示例方案.txt 片段 1」来源）→ 意见「P2 和 P3 合并」得 5 页（3.0s）→ 确认，任务页数 6 → 5。

## 环境与边界说明

- **浏览器 + 真实模型未单独验收**：浏览器用例运行本地 Planner 并修饰响应；真实模型经 API 全流程验证。本地开发 API 读取 `.env` 发生在启动时，修改后需重启 `npm run dev:api`。
- 模型可能在「增加一页」与已有同类页面之间产生重复（如两页「后续规划」），需用户确认前检查；属模型质量问题，不影响结构校验。
- 页面内容生成（Content Agent）、流式输出、DeepSeek Harness 运行时、多 Agent 编排不在本阶段。
