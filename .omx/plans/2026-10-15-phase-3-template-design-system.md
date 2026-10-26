# Phase 3 计划:公司模板解析与 Design System(主题级)

日期:2026-10-15。本文为实施计划,基于设计文档、当前源码静态核对与既定契约变更;范围已经用户确认为「主题级应用」。

## 结论与依据

本阶段实施设计文档第 84 节的 Phase 3:公司模板解析 → Design System。目标是将已上传、已关联但从未被消费的公司模板 PPTX 解析为主题级设计系统(颜色、标题/正文字体、页面尺寸、版式清单),存入 0001 迁移即已建好的 `ppt_design_system.design_json`,并在导出 PPTX 时解析项目关联模板为 `DeckSpec.theme` 与 `DeckSpec.slide_size`,由渲染器套用。

依据:[原设计文档](../../个人%20PPT%20智能体项目设计文档.md)第 2700 行(开发顺序)、第 1000 行(公司模板处理)、第 1051 行(模板与布局关系)、第 2539 行(模板约束:品牌色/字体不允许 AI 修改)。

范围确认(用户 AskUserQuestion):仅主题级——颜色、标题/正文字体、页面尺寸、版式清单(仅记录,供后续阶段);不做 Logo/背景图提取,不做占位符/字号映射,不做 clrMap 重映射。

## 当前代码与接入点

| 能力 | 当前证据 | 本阶段动作 |
| --- | --- | --- |
| 模板存储 | [routes.py](../../apps/api/src/slidemind_api/routes.py) `POST /templates` 保存对象与记录,扩展名限 `pptx` | 上传后同步解析,状态 UPLOADED → READY/FAILED |
| 设计系统表 | [models.py](../../apps/api/src/slidemind_api/models.py) `DesignSystem` 自 0001 已存在,零代码引用 | 启用:每次成功解析追加一行,按 version 最新生效 |
| 主题契约 | [page.py](../../packages/schemas/src/slidemind_schemas/page.py) `Theme` 单一 `font_family`,渲染器几何 13.333×7.5 写死 | 拆分 `title_font_family`/`body_font_family`,新增 `DeckSpec.slide_size` |
| 导出链路 | [page_routes.py](../../apps/api/src/slidemind_api/page_routes.py) `render()` 构建 DeckSpec 不传 theme,走默认 | 新增 `resolve_design`:项目模板 → 校验 → Theme + SlideSize |
| PPTX 解析 | [parsers.py](../../apps/document-parser/src/slidemind_parser/parsers.py) 已有 `_validate_archive` 限界与错误惯例,但无人读 theme1.xml | 新增 `extract_template_design`:zip + ElementTree 提取主题 |
| 渲染器 | [render.mjs](../../apps/ppt-renderer/src/render.mjs) Theme 已按请求消费,`fontFace` 取 `theme.font_family` | 动态 `defineLayout`,标题/正文字体分流 |
| 工作台 | [PageEditor.tsx](../../apps/web/src/PageEditor.tsx) 提示"上传的公司模板尚未应用" | 模板解析状态/重试、项目模板关联可修改、主题来源提示 |

约束:main.py CORS 仅允许 GET/POST,项目模板关联端点用 `POST /projects/{id}/template`,不得用 PATCH。

## 需求与阶段范围

交付「上传模板 → 同步解析(失败可重试)→ design_json 落库 → 项目关联模板 → 导出时套用主题」的完整链路。

- 解析项:presentation.xml 的 sldSz(EMU,5–56 英寸);theme1.xml 的 clrScheme(dk1/lt1/accent1 必需,dk2/lt2/accent2..6 可选)与 fontScheme(majorFont/minorFont,ea 优先、latin 回退);slideLayouts 清单(name + type,仅记录)。
- 诚实原则:必需颜色或字体缺失 → 解析 FAILED 与可行动错误信息,不造配色、不回退默认字体;模板状态与错误对前端可见、可重试。
- 导出回退:无模板、解析失败或 design_json 校验异常 → 默认主题 + 响应 `themeSource="default"`(前端提示);模板安全等级超出当前授权 → 403(同来源引用惯例)。
- 不变式:模板与素材/资料分离;design_json 只增不改;渲染回退不静默。

## 实施顺序

1. **契约**。`packages/schemas` 新增 `design.py`(`TemplateDesign`/`LayoutInfo`,含 EMU 界限);`page.py` 的 `Theme` 拆分字体、新增 `SlideSize`;`DeckSpec.slide_size` 以 `json_schema_extra` 暴露默认值(Ajv useDefaults 依赖);重导出 deck.schema.json。
2. **解析器**。`apps/document-parser` 新增 `template_design.py`,复用 `MAX_INPUT_BYTES`/`_validate_archive`/`_DocumentError`;版式按数字排序;多母版只认 theme1;全部异常收敛为可行动错误。
3. **API**。`Template.processing_error`(迁移 0003);上传后同步解析、始终 201;`POST /templates/{id}/process` 幂等重试;`POST /projects/{id}/template` 设/改/清关联;`resolve_design` 接入 render() 并扩展响应(themeSource/themeName)。
4. **渲染器**。`render.mjs` 动态尺寸 defineLayout;页标题/副标题/块标题用 title 字体,正文/页脚用 body 字体。
5. **工作台**。模板 tab 状态徽标/错误/重试解析;项目区模板选择与应用;PageEditor 主题来源提示与诚实回退提示。
6. **验收**。解析/API/渲染器/e2e 测试;README 与 architecture 更新;`docs/phase3-verification.md` 记录真实模板验收结果。

## 建议验收标准

- 固定样例模板解析出的颜色、字体、页面尺寸与 OOXML 原文一致;sysClr、小写 srgbClr、ea 空回退 latin 均正确;缺失必需槽位、损坏、加密、越界尺寸均给出可行动错误且可重试。
- 上传始终 201;解析成功后 `ppt_design_system` 按 version 追加;重解析后渲染使用最新 design_json。
- 关联 READY 模板的项目导出:RecordingRenderer 收到的 deck.theme/slide_size 与模板一致,响应 `themeSource="template"`;下载的 PPTX slide XML 含模板 accent1 颜色与标题/正文字体,presentation.xml 的 cx/cy 与模板页面尺寸一致。
- 无模板、FAILED 模板 → 默认主题 + `themeSource="default"`;模板超出授权等级 → 403;既有导出、下载、版本冲突、来源校验回归全部通过。
- `POST /projects/{id}/template` 可设、改、清关联;非法或越权模板 → 404。
- `schema:check` 通过;font_family 在 schema 与渲染器中无残留。

## 风险与处理

- **Ajv useDefaults 不注入嵌套默认**:`slide_size` 必须带 `json_schema_extra={"default": ...}`(先例 page.py theme 字段);渲染器只在 parseDeck 之后读取 deck.slide_size。
- **PptxGenJS 只写 `a:latin`**:CJK 字形可能绑定查看端主题 ea 字体;提取时优先 ea 最小化偏差,`render:example` 人工目检;后处理补写 `a:ea` 明确不在本期。
- **模板字体在查看机器缺失**:客户端回落属正常;design_json 与 Theme 保存真实值,不虚构。
- **同步解析时长**:仅 XML、受 `MAX_INPUT_BYTES`/`_validate_archive` 限界,默认上传上限 25MB 内可接受;不引入 worker 与租约。
- **并发重复解析**:可能追加同 version 行;渲染取 `(version desc, id desc)` 首行,结果确定。
- **schema 破坏性变更**:`font_family` 移除影响 deck.schema.json 全部消费方;`schema:check` 与渲染器测试把守,theme 从不持久化,无存量数据风险。

## 验证安排

新增 `tests/test_template_design.py`(解析单测,手工构造最小 PPTX zip)、`tests/test_templates.py`(上传/重试/落库/渲染主题/403/项目模板关联)、`tests/e2e/template.spec.ts`(JSZip 构造模板 → 上传 → 建项目 → UI 导出下载 → 解包断言颜色与尺寸);渲染器测试补充字体分流与动态尺寸断言。

完成后运行 `npm run schema:check`、`npm run test:api`、`npm run lint:python`、`npm test`、`npm run build`、`npm run test:e2e`;`render:example` 目检中文字体;最终以真实公司模板 PPTX 走一次端到端并记录于 `docs/phase3-verification.md`。
