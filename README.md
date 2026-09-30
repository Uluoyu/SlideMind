# SlideMind

个人 PPT 智能体工作台。基于[项目设计文档](./个人%20PPT%20智能体项目设计文档.md)，已实现基础框架与 Phase 2 文档解析、项目 RAG。

已打通：**创建项目 → 上传资料/素材/模板 → 创建 PPT → 生成与确认大纲 → 编辑页面草稿 → 导出并下载 PPTX**。

资料库已支持 **上传 → 后台解析 → 分块和向量入库 → 混合检索 → 重排 → 查看原文来源**。PDF 保留页码，PPTX 保留幻灯片编号，DOCX 保留段落/表格位置；TXT、Markdown 同样可检索。

当前 PPT 大纲和页面仍使用本地规则，检索结果尚未自动填入页面；公司模板尚未自动应用，导出使用默认主题。页面中的项目结论和数据仍需用户补充与核实。

## 快速启动

依赖：Python 3.11+、[uv](https://docs.astral.sh/uv/getting-started/installation/)、Node.js 22+。在仓库根目录执行：

```sh
uv sync --locked
npm ci
npm run db:migrate
```

无配置时默认使用 `data/slidemind.db` 与 `data/storage/`，不需要 Docker。新安装可复制 `.env.example` 为根目录 `.env` 并配置服务；已有 `.env` 请保留并按需修改。已有安装也必须执行 `npm run db:migrate` 升级资料处理字段。

当前开发工作区已配置内网 PostgreSQL、MinIO 和模型服务，远程数据库已迁移到 `0002`，可直接启动应用。实际 PostgreSQL 16.15 + pgvector 0.8.6、MinIO、Embedding 和 Reranker 的完整文档检索流程已验证，详见 [Phase 2 验收记录](./docs/phase2-verification.md)。

分别打开三个终端，均在仓库根目录运行：

```sh
# API，http://127.0.0.1:8000
npm run dev:api

# PPT 渲染器，http://127.0.0.1:3001
npm run dev:renderer

# 工作台，http://127.0.0.1:5173
npm run dev
```

打开 <http://127.0.0.1:5173>。API 文档位于 <http://127.0.0.1:8000/docs>。

1. 创建项目，按需上传资料、图片和公司模板。项目资料自动处理为“可检索”，失败时显示原因并支持重试。
2. 创建 PPT 任务，填写主题、页数、汇报对象及重点。
3. 生成初始大纲，调整标题、用途、顺序和页数，确认并保存。
4. 生成页面草稿，逐页编辑标题、副标题、布局和正文，保存当前页。
5. 点击“生成 PPTX”，完成后点击“下载 PPTX”。

已确认大纲保持只读；页面内容可以反复修改。修改后必须重新导出，旧版本下载会失效。刷新或重启服务后仍可读取项目、页面和导出结果。

## 资料检索与模型服务

在“资料与模板 → 项目资料”上传文件，待状态为“可检索”后搜索问题，点击“查看来源”读取原文片段和位置。重新索引期间该资料暂不参与搜索，旧来源链接不会指向新片段。

当前内网配置：

| 服务 | 地址 | 配置 |
| --- | --- | --- |
| Embedding | `http://172.16.1.212:6068/v1/embeddings` | `qwen3_embedding`，1024 维 |
| Reranker | `http://172.16.1.212:6066/v1/rerank` | `qwen3_reranker`，`qwen3` 输入格式 |

Qwen3 Embedding 的查询会添加检索指令，原文保持原样。当前 Reranker 的成对评分接口需要 Qwen3 判定模板；如果服务端已应用该模板，将 `SLIDEMIND_RERANKER_INPUT_FORMAT` 改为 `plain`，避免重复添加。认证可通过两项 `*_API_KEY` 配置，密钥只保存在服务端。

重排服务失败时保留混合检索结果并明确提示；Embedding 失败则标记索引失败或返回检索错误，不写入假向量。项目和安全等级过滤在向量计算、排名及向外部重排服务发送候选资料前执行。更换向量模型、维度或模型版本后需点击“重新索引”；同名模型更新权重时请更新 `SLIDEMIND_EMBEDDING_REVISION`。

可选本地模型：`SLIDEMIND_EMBEDDING_PROVIDER=local`、`SLIDEMIND_EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5`、`SLIDEMIND_RETRIEVAL_MIN_SIMILARITY=0.5`。首次索引时 FastEmbed 下载 ONNX 模型至 `.cache/fastembed`，后续复用缓存；无需本地模型时使用 HTTP provider，不会加载本地权重。留空 `SLIDEMIND_RERANKER_URL` 可仅使用混合检索。

扫描文档 OCR、图片语义检索、XLSX 内容解析尚未支持。旧 XLSX 上传接口保留，但处理会明确提示转换为支持的格式。公司模板和图片素材保持独立存储，不自动作为项目文档索引。

## 验证

```sh
npm run test:api
npm run lint:python
npm run schema:check
npm test
npm run build
npm run test:e2e
```

浏览器测试启动独立 API、Renderer 与 Vite，使用 8001、3002、5174 端口，数据写入 `artifacts/e2e/`，不使用本地工作数据。Windows 默认使用已安装的 Edge；其他平台先运行 `npx playwright install chromium`。可用 `PLAYWRIGHT_CHANNEL` 环境变量指定已安装浏览器，例如 `chrome`。

普通 Python 测试替换外部模型调用，仍实际执行解析、迁移、存储、任务及查询。浏览器资料库用例调用当前配置的实际模型服务。额外验收可在 PowerShell 中运行：

```powershell
$env:SLIDEMIND_TEST_REMOTE_MODELS='1'
uv run pytest tests/test_remote_integration.py -q -s
# 可选：实际 MinIO 上传/解析/检索验收；仅清理本次上传的随机对象。
$env:SLIDEMIND_TEST_MINIO='1'
uv run pytest tests/test_remote_integration.py -q -s
# 只针对空的、可丢弃的 PostgreSQL 测试库；每次建立并清理独立 schema。
$env:SLIDEMIND_TEST_POSTGRES_URL='postgresql+psycopg://slidemind:slidemind@localhost:5432/slidemind_test'
uv run pytest tests/test_pgvector.py -q
```

实际 PostgreSQL 16.15 + pgvector 0.8.6 已通过迁移、维度、项目隔离及重新索引检查；PostgreSQL + MinIO + 两个模型服务已通过 PDF 上传、后台索引、API 重启、检索重排及原文追溯验证。详细范围见 [Phase 2 验收记录](./docs/phase2-verification.md)。

只验证渲染器也可运行：

```sh
npm run render:example
```

输出为 `artifacts/starter.pptx`。PPT 文本是可编辑文本；引用信息写入备注。

## 可选基础设施

```sh
docker compose -f deploy/compose/compose.yml up -d
```

将根目录 `.env` 对应配置改为：

```dotenv
SLIDEMIND_DATABASE_URL=postgresql+psycopg://slidemind:slidemind@localhost:5432/slidemind
SLIDEMIND_STORAGE_BACKEND=minio
```

再次执行 `npm run db:migrate`，重启 API。Compose 提供 PostgreSQL 16 + pgvector、MinIO 与桶初始化；应用进程仍在本机运行。PostgreSQL 与 SQLite 是两套独立数据，不会自动迁移已有项目。MinIO 控制台为 <http://localhost:9001>，本地开发凭据见 `.env.example`。

## 目录与进度

| 目录 | 职责及当前状态 |
| --- | --- |
| `apps/web` | React + TypeScript 工作台，项目/资料/大纲/页面编辑/下载 |
| `apps/api` | FastAPI、SQLAlchemy、Alembic，项目隔离及持久化 |
| `apps/agent` | 本地大纲规划器、页面草稿生成器、工作流状态定义 |
| `apps/ppt-renderer` | PptxGenJS 独立服务，支持封面、双栏、总结布局 |
| `apps/rag` | HTTP/本地 Embedding、HTTP Reranker、中文关键词与向量混合排名 |
| `apps/document-parser` | PDF/DOCX/PPTX/TXT/MD 文本解析、来源位置和分块 |
| `apps/vision-qa` | 视觉检查协议，尚未接入图像转换或模型 |
| `packages/schemas` | Pydantic Page JSON 与导出的 JSON Schema |
| `packages/common` | 安全等级等共享规则 |
| `deploy/compose` | 可选 PostgreSQL/pgvector 与 MinIO |

架构、API 契约及后续接入点见 [docs/architecture.md](./docs/architecture.md)。本阶段不代表设计文档中的完整 MVP：公司 Design System 提取、素材自动选择、模型规划与证据驱动的正文生成、PDF/PNG 预览、Vision QA 和自动修复仍待实现。

## 常见问题

- API `/health` 检查进程；`/ready` 检查数据库表是否可用。若未就绪，先执行迁移。
- 导出返回 503 时，确认渲染器已启动、`SLIDEMIND_RENDERER_URL` 正确，以及存储可写。页面会保留，可重新导出。
- 页面保存提示版本冲突时，保留需要的修改文本，刷新后重新编辑。接口用版本号阻止旧页面覆盖新内容。
- 资料处理失败时先看文件旁的原因；模型服务恢复后点击“重试处理”。正常关闭会重新排队当前任务，意外退出的任务在租约到期后恢复（默认 120 秒）。
- 修改 Pydantic 页面契约后运行 `npm run schema:export`，同步提交 `packages/schemas/deck.schema.json`；`schema:check` 用于检查漂移。
- `.env` 由 Python API 读取；Node 渲染器端口通过进程环境变量 `RENDERER_PORT` 配置。Vite 代理默认指向 8000，可通过 `SLIDEMIND_API_PROXY` 修改。
- 当前是本机单用户模式，没有登录与多租户认证。项目过滤用于防止资料串用，不能代替用户身份校验。部署到共享网络前需要补认证、授权与受保护的服务入口。
