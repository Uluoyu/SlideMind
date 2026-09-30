# 下一阶段建议：Phase 2 文档解析与项目 RAG

日期：2026-09-29。本文为开发建议，基于设计文档和当前源码静态核对；未在本次规划中重新运行测试。

## 结论与依据

下一阶段应实施设计文档第 84 节的 Phase 2：PDF/PPTX/DOCX 解析 → 文本分块 → Embedding → RAG。目标是让已上传资料成为可检索、可追溯的项目证据，为后续模板解析、模型策划和内容生成提供输入。

依据：[原设计文档](../../个人%20PPT%20智能体项目设计文档.md)第 2700 行（开发顺序）、第 1864 行（解析流程）、第 1916 行（混合检索）、第 2012 行（事实来源）。

当前完成的是基础业务闭环，完整 MVP 仍需补齐资料理解、模板应用、真实内容生成、素材选择、预览和基础 QA；完整验收见原设计文档第 2217、2750 行。

## 当前代码与接入点

| 能力 | 当前证据 | 下一步 |
| --- | --- | --- |
| 上传资料 | [routes.py](../../apps/api/src/slidemind_api/routes.py)第 92、133 行：保存对象和文件记录 | 上传后创建解析与索引任务 |
| 文件解析 | [contracts.py](../../apps/document-parser/src/slidemind_parser/contracts.py)第 6、11 行：只有 ParsedSection 和 DocumentParser 协议 | 实现格式解析器和调度入口 |
| 文本与向量存储 | [models.py](../../apps/api/src/slidemind_api/models.py)第 68 行：DocumentChunk 已含文本、页码、Metadata、embedding | 实现写入、重建与检索所需迁移 |
| RAG | [contracts.py](../../apps/rag/src/slidemind_rag/contracts.py)第 9、15、21 行：过滤上下文、Retriever、Embedder 协议 | 实现真实 Embedding 和混合检索 |
| 来源契约 | [page.py](../../packages/schemas/src/slidemind_schemas/page.py)第 10 行：文件 ID、文件名、页码、摘录 | 从真实分块构建引用，不能由模型随意填写 |
| 大纲与正文 | [planner.py](../../apps/agent/src/slidemind_agent/planner.py)第 25 行和 [pages.py](../../apps/agent/src/slidemind_agent/pages.py)第 7 行：规则大纲及待补充正文 | 在后续模型阶段消费检索证据 |

## 需求与阶段范围

本阶段交付“上传资料 → 解析 → 分块 → 索引 → 按项目搜索 → 查看来源”。先服务项目知识库；公司知识库、历史页面设计知识库保持原有模块边界，分阶段接入。

支持文本型 PDF、DOCX、PPTX，以及用于快速贯通流程的 TXT/Markdown。PDF 保留页码，PPTX 保留幻灯片编号；DOCX 使用段落或标题位置元数据，不伪造渲染页码。扫描 PDF 的 OCR、图片语义检索和历史 PPT 视觉布局分析安排在后续扩展；本阶段对无法提取文本的文件给出明确状态。

## 实施顺序

1. **资料处理任务与状态。** 在现有 API、文件模型和 Alembic 迁移基础上增加持久化处理状态、错误信息和重试入口。建议状态为 UPLOADED → PARSING → INDEXING → READY，失败进入 FAILED。采用单机 worker 即可；进程重启后能恢复或明确重试中断任务，模型和解析操作不长期占用业务写事务。
2. **格式解析。** 扩展 `apps/document-parser/src/slidemind_parser/`：先用 TXT/Markdown 打通，再完成文本型 PDF、DOCX 和 PPTX 的正文与表格文本提取。文件流通过现有 ObjectStore 获取。损坏文件、空文件和暂不支持的类型返回可理解的错误。
3. **分块与来源。** 在解析模块增加按标题、段落和长度预算分块的实现，写入现有 DocumentChunk。保留文件、位置和原文；重复执行同一处理任务不产生重复分块，失败或重建期间不暴露半成品索引。先不设计图片和复杂版式元素。
4. **Embedding 与索引。** 在 `apps/rag/src/slidemind_rag/` 实现 Embedder；记录模型名称、版本和维度，避免模型切换后混用向量。采用已有 [Compose 配置](../../deploy/compose/compose.yml)中的 PostgreSQL + pgvector 完成真实索引验证；SQLite 可继续承担基础开发和测试，但不能代替 pgvector 集成验收。开发时选定一种真实 Embedding 实现并验证中文检索。
5. **项目级混合检索。** 实现 Retriever，将关键词与向量结果融合。两条检索路径均先通过数据库中的文档归属和服务端安全等级过滤，再排名和截断；仅检索 READY 的有效索引。返回 SourceReference，并通过独立查询接口提供原始分块详情。无匹配时返回空结果，不补造项目事实。
6. **工作台接入与验收。** 扩展 [Library.tsx](../../apps/web/src/Library.tsx)、[api.ts](../../apps/web/src/api.ts)及 API 路由，展示处理状态、错误、重试按钮、查询框和检索结果；可查看命中文件、真实位置和摘录。来源查看入口同样执行项目与安全等级检查。此时用户能独立验证资料是否被正确理解和检索。

## 建议验收标准

- 每种支持格式至少一个固定样例能产生非空分块；PDF/PPTX 的来源页号与样例一致，DOCX 不生成虚假页号。
- 同一任务重复处理不增加重复分块；失败后可重试，服务重启后任务不会永久显示处理中。
- 预先标注 10 条中文资料查询，至少 8 条在 Top 5 中命中对应证据；关键词精确匹配与语义改写均包含在样例中。
- 项目 A 查询不能出现项目 B 的文本、引用或分块详情；超出服务端安全等级的资料也不能出现，包括关键词和向量召回路径。
- 检索摘录可在对应原文分块找到；构造明确无关查询时返回空结果或明确无匹配，不产生虚构内容。
- 前端完成上传、查看处理状态、检索和查看来源；损坏文档与 Embedding 故障均显示错误并可重试。
- 既有项目创建、大纲确认、页面编辑、PPTX 导出和下载行为通过现有回归检查。

## 风险与处理

- 中文检索可能受分词与向量模型影响：使用包含项目名、缩写、数字和语义改写的固定查询集评估，不仅检查接口是否返回结果。
- 文档分块可能丢失来源关系：保存位置元数据及原文，引用由服务端构建，分别校验 PDF 页码和 PPTX 页号。
- 上传、解析、索引可能部分成功：使用持久化任务、幂等处理和有效索引切换；只将完整成功的处理结果标记 READY。
- pgvector 与 SQLite 行为不同：增加实际 PostgreSQL 集成测试，确认向量维度、查询和过滤行为；保留已有 SQLite 基础测试。

## 验证安排

实施时增加解析/分块单测、实际 PostgreSQL 检索集成测试、跨项目与安全等级 API 测试，以及资料库浏览器流程测试。

完成后运行仓库现有 `npm run test:api`、`npm run lint:python`、`npm run schema:check`、`npm test`、`npm run build`、`npm run test:e2e`；新增的 PostgreSQL 集成验收单独记录真实运行结果。涉及 Schema 扩展时同步导出并校验 Python 与 Node 契约。

## 后续顺序

按原设计第 84 节及 [当前架构文档](../../docs/architecture.md)第 99 行衔接：

1. Phase 3：公司模板解析为 Design System，并让已支持的 Renderer 布局实际使用主题规则。
2. Phase 4–5：为 Planner 增加真实模型实现，完成基于检索证据的 Content Agent 与实际素材选择；缺失证据明确提示待补充。
3. Phase 6：沿用已有 Page JSON 与 PPTX 闭环，按内容需求扩展布局和素材渲染。
4. Phase 7–8：实际 PPT 转 PDF/PNG 预览及基础视觉 QA，达到完整 MVP 的展示与检查要求。
5. 更后续：自动修复、历史 PPT 设计检索，以及原设计 V2/V3 的增强能力。

第一个可独立验收的开发切片：上传一份文本型 PDF → 解析并分块 → 持久化 → 查询命中 → 展示真实文件名、页码和摘录，然后扩展格式与混合检索能力。
