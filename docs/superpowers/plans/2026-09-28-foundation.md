# SlideMind 基础框架实施计划

> 按 superpowers:executing-plans 在当前工作区逐项实施；现有未提交代码是本次工作的基础。

**目标：** 在已有项目、文件、大纲能力上，打通可编辑页面草稿到可下载 PPTX 的本地工作流。

**架构：** React 工作台通过 FastAPI 管理状态与持久化。Python PageSpec 是页面契约，Node/PptxGenJS 仅负责确定性渲染；文件统一经 ObjectStore 读写。

**技术栈：** React / TypeScript、FastAPI / Pydantic、SQLAlchemy / Alembic、PptxGenJS / Ajv；默认 SQLite 和本地存储，可选 PostgreSQL / pgvector 与 MinIO。

**设计依据：** [个人 PPT 智能体项目设计文档](../../../个人%20PPT%20智能体项目设计文档.md)，重点为第 23、38、49–55、75、84 节。

## 约束

- 不将基础框架宣称为完整 MVP。大纲和页面草稿使用本地规则，不能编造项目数据、伪称检索或模板解析已完成。
- 保留项目隔离和服务端安全等级过滤；页面来源引用必须属于当前项目且在权限范围内。
- 首先支持 title、two_column、summary 三种布局，JSON 校验保持 Python 与 Node 一致。
- 默认无需 Docker、模型密钥即可运行；不覆盖用户现有改动。
- 内容改变后旧导出失效；渲染失败保留页面并允许重试；重复生成不得悄悄覆盖编辑。

## Task 1：渲染契约与默认值

**文件：** `apps/ppt-renderer/src/render.mjs`、`apps/ppt-renderer/test/render.test.mjs`、`packages/schemas/src/slidemind_schemas/page.py`。

- [x] 复现默认主题缺失测试失败；确认 Pydantic default_factory 未导出 JSON default。
- [x] 在 Pydantic 契约中显式导出主题和列表 default，由共享 Schema 填充 Node 缺失值。
- [x] 增加空白标题拒绝测试，补充字符串裁剪与连续页码校验。
- [x] 运行 `npm test`、Schema 一致性检查。

## Task 2：页面与导出 API

**文件：** `apps/api/src/slidemind_api/page_routes.py`、`rendering.py`、`contracts.py`、`storage.py`、`config.py`、`main.py`，`apps/agent/src/slidemind_agent/pages.py`，`tests/test_pages.py`。

**接口：** `GET /documents/{id}/pages` 返回页面状态及 PageSpec；`POST /documents/{id}/pages/generate` 生成缺失页面；`POST /documents/{id}/pages/{pageNo}` 保存单页；`POST /documents/{id}/render` 导出；`GET /documents/{id}/download` 下载。所有接口必须携带 `projectId`。

- [x] 先增加测试：未确认大纲不能生成；跨项目请求返回 404；修改页面持久化并使导出失效；渲染失败可重试；禁止跨项目/越权引用。
- [x] 本地生成器仅将已确认标题、用途转换为页面草稿，正文提示用户补充证据，不生成业务结论。
- [x] 提供存储读取和可替换 Renderer 协议，默认 HTTP 客户端连接 `http://127.0.0.1:3001`。
- [x] 将渲染结果验证为 PPTX 后保存；成功才更新 COMPLETED，失败保留页面并返回明确错误。
- [x] 运行后端回归测试，覆盖服务重启后重新读取页面和导出。

## Task 3：工作台闭环

**文件：** `apps/web/src/PageEditor.tsx`、`api.ts`、`App.tsx`、`OutlineEditor.tsx`、`styles.css`，`tests/e2e/workspace.spec.ts`、`playwright.config.ts`。

- [x] 大纲确认后提供生成页面入口及页面列表。
- [x] 表单编辑标题、副标题、布局和正文，预览为结构示意；显示保存状态与错误。
- [x] 支持保存、渲染与下载，未保存内容阻止导出或切换导致的数据丢失。
- [x] 用实际 API 和 Renderer 验证创建项目 → 确认大纲 → 编辑 → 渲染 → 下载 → 刷新。

## Task 4：运行与扩展文档

**文件：** `README.md`、`docs/architecture.md`、`.env.example`、`package.json`。

- [x] 写明依赖安装、迁移、三个服务启动、测试命令及可选基础设施。
- [x] 说明现有功能、模型/RAG/模板/预览/QA 后续接入点与安全边界。
- [x] 最终执行 Python 测试、Ruff、Schema check、Node 测试、前端构建、浏览器流程测试。

## 审查补充

- 修复再次导出失败后的前端旧状态，新增浏览器失败/重试测试。
- 统一实际请求 2 MiB 预算，超限在状态改变前返回 422；测试包括 UTF-8 中文摘录及 HttpRenderer 输入边界。
- 增加实际并发保存与渲染竞争测试，确认不发布过期内容，重试保存后旧下载失效。

验收结果：Python 15 项、Node 4 项、Playwright 2 项通过；Ruff、Schema check、前端构建通过。生成 `artifacts/starter.pptx`，浏览器验收截图保存于 `artifacts/workspace-desktop.png` 与 `artifacts/workspace-mobile.png`。PostgreSQL/MinIO、真实模型和视觉 QA 未在本阶段运行。
