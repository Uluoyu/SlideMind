# SlideMind

个人 PPT 智能体工作台。基于[项目设计文档](./个人%20PPT%20智能体项目设计文档.md)，当前提供可运行的基础框架。

已打通：**创建项目 → 上传资料/素材/模板 → 创建 PPT → 生成与确认大纲 → 编辑页面草稿 → 导出并下载 PPTX**。

当前大纲和页面使用本地规则，无需模型密钥。上传的资料尚未解析或参与生成，公司模板尚未自动应用；导出使用统一的默认主题。页面中的项目结论和数据需要用户补充与核实。

## 快速启动

依赖：Python 3.11+、[uv](https://docs.astral.sh/uv/getting-started/installation/)、Node.js 22+。在仓库根目录执行：

```sh
uv sync --locked
npm ci
npm run db:migrate
```

默认使用 `data/slidemind.db` 与 `data/storage/`，不需要 Docker。需要自定义配置时，将 `.env.example` 复制为根目录的 `.env`。

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

1. 创建项目，按需上传资料、图片和公司模板。
2. 创建 PPT 任务，填写主题、页数、汇报对象及重点。
3. 生成初始大纲，调整标题、用途、顺序和页数，确认并保存。
4. 生成页面草稿，逐页编辑标题、副标题、布局和正文，保存当前页。
5. 点击“生成 PPTX”，完成后点击“下载 PPTX”。

已确认大纲保持只读；页面内容可以反复修改。修改后必须重新导出，旧版本下载会失效。刷新或重启服务后仍可读取项目、页面和导出结果。

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
| `apps/rag` | 检索与 Embedding 协议，尚未接入实现 |
| `apps/document-parser` | 文档解析协议，尚未接入格式解析器 |
| `apps/vision-qa` | 视觉检查协议，尚未接入图像转换或模型 |
| `packages/schemas` | Pydantic Page JSON 与导出的 JSON Schema |
| `packages/common` | 安全等级等共享规则 |
| `deploy/compose` | 可选 PostgreSQL/pgvector 与 MinIO |

架构、API 契约及后续接入点见 [docs/architecture.md](./docs/architecture.md)。本阶段不代表设计文档中的完整 MVP：文档解析/RAG、公司 Design System 提取、素材自动选择、模型规划、PDF/PNG 预览、Vision QA 和自动修复仍待实现。

## 常见问题

- API `/health` 检查进程；`/ready` 检查数据库表是否可用。若未就绪，先执行迁移。
- 导出返回 503 时，确认渲染器已启动、`SLIDEMIND_RENDERER_URL` 正确，以及存储可写。页面会保留，可重新导出。
- 页面保存提示版本冲突时，保留需要的修改文本，刷新后重新编辑。接口用版本号阻止旧页面覆盖新内容。
- 修改 Pydantic 页面契约后运行 `npm run schema:export`，同步提交 `packages/schemas/deck.schema.json`；`schema:check` 用于检查漂移。
- `.env` 由 Python API 读取；Node 渲染器端口通过进程环境变量 `RENDERER_PORT` 配置。Vite 代理默认指向 8000，可通过 `SLIDEMIND_API_PROXY` 修改。
- 当前是本机单用户模式，没有登录与多租户认证。项目过滤用于防止资料串用，不能代替用户身份校验。部署到共享网络前需要补认证、授权与受保护的服务入口。
