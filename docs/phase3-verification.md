# Phase 3：公司模板解析与 Design System 验收记录

日期：2026-10-15。依据：[实施计划](../.omx/plans/2026-10-15-phase-3-template-design-system.md)、[项目设计文档](../个人%20PPT%20智能体项目设计文档.md)第 25、80、84 节。范围为用户确认的「主题级应用」：颜色、标题/正文字体、页面尺寸与版式清单；Logo/背景图提取和占位符级布局映射不在本阶段。

## 已实现能力

| 验收项 | 实现与证据 |
| --- | --- |
| 模板解析 | 直接读取 PPTX XML：presentation.xml 尺寸、theme 配色（srgbClr/sysClr）、majorFont/minorFont（ea 优先、latin 回退）、版式清单（数字排序）；复用 Phase 2 的输入限界、加密与 ZIP 炸弹防护 |
| 设计系统 | `ppt_design_system`（0001 已建表）按版本追加存储 `TemplateDesign`；每次成功解析 version 递增，渲染取 `(version, id)` 倒序最新行；并发重复解析结果确定 |
| 诚实失败 | 必需配色/字体缺失、损坏、加密、尺寸越界（5–56 英寸）→ FAILED 与可行动中文原因，不造配色、不写默认字体；上传始终 201（文件已存储） |
| 导出应用 | `render()` 经 `resolve_design` 将项目模板映射为 Theme（accent1→主色、lt1→背景、dk1→文字）与 SlideSize（EMU→英寸），在状态变更前解析 |
| 回退边界 | 未关联、未就绪或 design_json 校验失败 → 默认主题 + `themeSource="default"`（前端提示）；模板超出安全授权 → 403 且不留状态副作用 |
| 渲染器 | 按请求 `defineLayout` 动态尺寸；页标题/副标题/块标题用标题字体，正文/页脚用正文字体；内容带随高度缩放，短版面（如 16:10）不越界、不与页脚重叠 |
| 项目关联 | `POST /projects/{id}/template` 可设/改/清（CORS 仅 GET/POST，遵循仓库全 POST 惯例）；工作台模板栏即时应用，模板库显示解析状态与重试 |

## 最终检查

| 检查 | 结果 |
| --- | --- |
| Python 全部测试 | **112 passed**，7 skipped（既有环境门控：pgvector/远程模型/MinIO）；含真实模板修复后新增的 2 条多母版回归测试 |
| Ruff、Schema 漂移检查 | 通过；`font_family` 已从契约与渲染器移除，无残留 |
| `npm test` | **9 passed**，实际 Renderer（含短版面越界回归测试） |
| `npm run build` | 前端 TypeScript/Vite、Renderer 均通过 |
| `npm run test:e2e` | workspace 2/2、**template 2/2 通过**；library 1 条环境性失败（见下） |

主要测试：[解析](../tests/test_template_design.py)、[模板 API 与渲染应用](../tests/test_templates.py)、[渲染器主题与尺寸](../apps/ppt-renderer/test/render.test.mjs)、[浏览器模板流程](../tests/e2e/template.spec.ts)。

浏览器验收覆盖：上传自建模板 →「可应用」→ 关联项目 → UI 导出 → 下载 PPTX 解包断言 slide XML 含模板 accent1、标题/正文字体与背景/文字色，presentation.xml 的 `cx/cy` 与模板页面尺寸一致；损坏模板显示「解析失败」与原因并可重试。

## 环境与边界说明

- **library 浏览器用例当日环境性失败**：内网 Embedding（172.16.1.212:6068）与 Reranker（:6066）均返回 502，资料索引因此失败；该用例按 README 设计依赖真实模型服务，与 Phase 3 改动无关（curl 证实两端点 502）。服务恢复后需复跑。
- **真实公司模板验收（2026-10-26）**：首次上传真实公司模板即解析失败「模板版式数量超过限制」。该模板含 21 个母版 / 211 个版式，但 21 套主题配色字体完全相同——是「保留源格式」粘贴幻灯片遗留的重复母版，3 张幻灯片全部挂在母版 1。修复：版式清单改为沿 `presentation.xml` 的 `sldMasterIdLst` 首项解析主母版，按其 `sldLayoutIdLst` 声明顺序列出版式；无法解析母版关系时回退原先的全量数字排序，100 上限保留（回归测试覆盖两种情况）。修复后经 `POST /templates/1/process` 重试为「可应用」，解析结果：16:9（12192000×6858000 EMU）、accent1 `#4472C4`、lt1 `#FFFFFF`、dk1 `#000000`、标题/正文字体均为微软雅黑、主母版 11 个版式。按 `resolve_design` 映射离线渲染导出，解包核对 slide XML 含上述颜色与字体，`sldSz` 为 12191970×6858000（13.3333 英寸序列化值，与默认 16:9 一致）。
  - 该模板主题配色为 Office 默认蓝橙色板，品牌色若只体现在母版背景/图片上，主题级应用无法提取——属于 Phase 3 已排除的 Logo/背景范围。
  - 多数版式 `type` 为 `unknown`（自定义版式未声明 type），对主题级应用无影响，占位符映射阶段需按名称/占位符识别。
- **页面尺寸**：16:9（13.3333×7.5）与 4:3 输出与之前逐字节一致；短版面（16:10 等）内容带按高度收缩。模板高度小于约 6 英寸且单栏 4 内容块时正文空间极小但不出界。
- **页脚文字**：沿用默认 `SlideMind`——页脚属于内容而非品牌元素，模板解析不改写；后续 Content Agent 阶段可按项目信息生成。
- **CJK 字体**：PptxGenJS 将 fontFace 同时写入 `a:latin/a:ea/a:cs`，中文绑定与模板一致；模板字体在查看机器缺失时由客户端回落，design_json 保存真实值。
- 模板解析为同步 XML 读取（默认上传上限 25MB 内），不占用模型服务，也不引入后台租约；多母版仅取 theme1 与主母版版式，`clrMap` 重映射为已接受限制，见实施计划。

## 数据与迁移

新增迁移 `0003`：`ppt_template.processing_error`（batch_alter_table，SQLite/PostgreSQL 双方言）。`ppt_design_system` 沿用 0001 既有表。已有安装执行 `npm run db:migrate` 即可；本地 SQLite 与远程 PostgreSQL 均适用。
