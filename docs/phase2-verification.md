# Phase 2：文档解析与项目 RAG 验收记录

日期：2026-09-30。依据：[实施计划](../.omx/plans/2026-09-29-phase-2-document-rag.md)及[项目设计文档](../个人%20PPT%20智能体项目设计文档.md)第 84 节。

Phase 2 功能已实现，原生 PostgreSQL、MinIO、Embedding 和 Reranker 的完整流程已验证。远程业务数据库已迁移到 `0002`，当前配置的应用启动及就绪检查通过。

## 已实现能力

| 验收项 | 实现与证据 |
| --- | --- |
| 格式解析 | 文本型 PDF、DOCX、PPTX、TXT、Markdown；损坏、加密、空文档及不支持格式返回明确错误 |
| 分块与来源 | 有界分块、重叠及原文字符偏移；PDF 真实页码、PPTX 幻灯片编号、DOCX 段落和表格位置 |
| 后台处理 | QUEUED/PARSING/INDEXING/READY/FAILED；租约续期、过期恢复、正常关闭重新排队、失败重试 |
| 索引一致性 | 分块替换与 READY 原子提交；模型和维度隔离；重建期间隐藏旧索引；旧来源 ID 不指向新分块 |
| 项目检索 | 先过滤项目、安全等级、READY 状态及模型标识，再融合关键词与向量；无关问题返回空结果 |
| 模型接入 | HTTP/本地 Embedding、HTTP Reranker；校验数量、顺序、维度及有限值；重排失败明确提示回退 |
| 工作台 | 自动更新处理状态、错误原因、重试、重新索引、搜索、来源面板及移动端布局 |
| 回归 | 既有项目创建、大纲确认、页面编辑、导出、下载、刷新恢复及失败重试通过 |

## 当前内网配置

连接信息已写入工作区根目录 `.env`，该文件由 Git 忽略；凭据未写入本文或配置示例。

| 服务 | 地址 | 状态 |
| --- | --- | --- |
| Embedding | `http://172.16.1.212:6068/v1/embeddings` | `qwen3_embedding`，1024 维，实际调用通过 |
| Reranker | `http://172.16.1.212:6066/v1/rerank` | `qwen3_reranker`，Qwen3 判定模板，实际调用通过 |
| PostgreSQL | `172.16.1.212:15432`，数据库 `postgres` | 16.15 + pgvector 0.8.6；业务表已迁移到 `0002`；实际向量检索通过 |
| MinIO | `http://172.16.1.212:19000`，桶 `slide` | 桶已存在；实际上传、读取、检索与测试对象清理通过 |

MinIO SDK 的 `SLIDEMIND_MINIO_ENDPOINT` 应填 `172.16.1.212:19000`，HTTP 对应 `SLIDEMIND_MINIO_SECURE=false`。

实际 Embedding 的 10 条固定中文查询测得 **Recall@5 = 10/10**，包含精确关键词和语义改写；无关问题“草莓蛋糕烘焙配方”无命中。此结果只代表小型固定验收集。

当前 Reranker 成对评分服务需要客户端添加 Qwen3 判定模板；订单异步处理证据得分约 **0.9935**，排在无关蛋糕配方之前。若服务端之后自行应用模板，将 `SLIDEMIND_RERANKER_INPUT_FORMAT` 改为 `plain`，避免重复添加。可选本地 FastEmbed 模型的实际缓存权重质量测试也通过，使用相似度阈值 0.5。

中文 PDF 全流程分别使用 LocalStore 和真实 MinIO 执行：上传 → 获取原始字节 → 解析 → 实际 Embedding → 检索与实际重排 → 查看原文；均命中真实第 2 页，来源内容与摘录一致。另有完整服务验收组合原生 PostgreSQL、MinIO 及两个实际模型，验证后台 worker 自动处理、1024 维向量入库、API 重启后仍可检索，以及跨项目查询和来源隔离。

## 最终检查

| 检查 | 结果 |
| --- | --- |
| Python 全部测试，启用实际本地模型、远程模型、MinIO 与原生 PostgreSQL/pgvector | **96 passed**，56.64 秒，无跳过 |
| Ruff、Schema 漂移检查 | 通过 |
| `npm test` | **4 passed**，实际 Renderer |
| `npm run build` | 前端 TypeScript/Vite、Renderer 均通过 |
| `npm run test:e2e` | **4 passed**，35.1 秒；资料库调用实际模型 |
| `git diff --check` | 通过 |
| 独立代码审查 | 未发现剩余重要问题；已修正任务关闭、旧租约批次检查及搜索长度不一致问题 |

本次 Python 测试有一条 Starlette/httpx 弃用提示及两条 Windows 模型缓存符号链接提示，不影响结果。桌面和 390px 移动端截图位于本地 `artifacts/library-desktop.png` 与 `artifacts/library-mobile.png`，已检查来源面板及横向溢出。

主要测试：[解析](../tests/test_parser.py)、[任务与隔离](../tests/test_ingestion.py)、[排名](../tests/test_rag.py)、[HTTP 适配器](../tests/test_remote_models.py)、[实际模型与 MinIO](../tests/test_remote_integration.py)、[pgvector](../tests/test_pgvector.py)、[浏览器资料库](../tests/e2e/library.spec.ts)。

复现完整可选检查需要先准备本地模型缓存和一个空的、可丢弃的 pgvector 测试库：

```powershell
$env:SLIDEMIND_TEST_REAL_EMBEDDINGS='1'
$env:SLIDEMIND_EMBEDDING_CACHE_DIR=(Join-Path (Get-Location) '.cache/fastembed')
$env:SLIDEMIND_TEST_REMOTE_MODELS='1'
$env:SLIDEMIND_TEST_MINIO='1'
$env:SLIDEMIND_TEST_POSTGRES_URL='postgresql+psycopg://slidemind:slidemind@localhost:5432/slidemind_test'
.venv/Scripts/python.exe -m pytest -q --basetemp .cache/pytest-final -o cache_dir=.cache/pytest-cache --tb=short
```

不设置可选开关时，普通测试会跳过这些外部服务验收。MinIO 验收只删除本次上传的随机对象，不清空桶；PostgreSQL 测试只创建和删除自己的随机 schema，拒绝公共 schema 已含 Alembic 版本表的数据库。

## 原生 PostgreSQL 与完整服务验收

原生 PostgreSQL **16.15** 已安装 pgvector **0.8.6**。两个原生集成用例独立执行通过，并再次纳入 96 项完整测试验证：

- 确定性向量用例验证实际 Alembic 迁移、向量维度、项目及安全等级过滤、其他项目异维向量排除，以及重新索引使旧来源失效。
- 实际模型用例通过 API 上传两页 PDF 到 MinIO，由后台 worker 解析并写入 1024 维 pgvector；关闭并重新创建 API 后，重排命中第 2 页证据，原文摘录一致，其他项目无法搜索或查看该来源。

测试在随机 schema 中运行，结束后删除各自 schema 与本次 MinIO 对象。完整测试后确认这些临时 schema 均已清理，远程公共 schema 原先没有 SlideMind 表，再执行业务数据库迁移。

业务迁移已执行 `0001 → 0002`，确认 `ppt_document_chunk.embedding` 的原生类型为 `vector`。随后使用工作区 `.env` 启动实际 API，`/health`、`/ready`、项目列表及 MinIO 桶访问均正常。当前没有遗留测试项目。

此前在没有原生数据库时使用过临时 PGlite 验证 SQL 路径；它忽略启动参数中的 `search_path`，测试连接已改为显式设置并断言 schema。这一临时服务已关闭，最终结果来自用户提供的原生 PostgreSQL。

当前检索采用精确余弦计算，没有建立 HNSW/IVFFlat 索引；本次验证针对个人资料规模及功能正确性，未执行大规模并发或性能压测。仓库自带 Compose 的独立启动过程未另行执行。

## 本地数据库与阶段边界

原本地 `data/slidemind.db` 已从 `0001` 升级到 `0002`，升级前使用 SQLite backup 备份到 `data/backups/slidemind-before-phase2-20260930-105751.db`，升级后记录数、完整性及外键检查通过。该本地数据库没有项目数据，无需向远程迁移用户资料。

当前 `.env` 按用户提供的配置指向内网 PostgreSQL/MinIO，迁移已完成，可直接启动或重启应用。需要临时使用本地数据库时，可仅将 `SLIDEMIND_DATABASE_URL` 改为 `sqlite:///./data/slidemind.db`；MinIO 和两个模型端点可继续使用。PostgreSQL 与 SQLite 的数据不会自动同步。后续重复原生集成测试请提供独立空测试库，不要将已迁移的业务库作为测试库。

扫描 PDF OCR、XLSX 解析、图片语义检索、历史 PPT 视觉分析未纳入本阶段。检索结果尚未自动填入 PPT 正文；后续仍需模板 Design System、模型规划、Content Agent、实际预览和 Vision QA。
