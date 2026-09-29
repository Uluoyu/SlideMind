# 个人 PPT 智能体项目设计文档

> 版本：V1.0
> 项目定位：公司模板约束下的个人 AI PPT 智能体
> 核心能力：资料理解 + RAG 检索 + PPT 策划 + 页面设计 + 素材选择 + PPT 自动生成 + 视觉检查 + 迭代优化

---

# 1. 项目概述

## 1.1 项目背景

日常工作中存在大量 PPT 制作需求，例如：

* 项目汇报
* 技术方案
* 客户方案
* 产品介绍
* 年度总结
* 员工述职
* 领导汇报
* 项目阶段汇报
* 招投标材料

传统 PPT 制作流程通常为：

```text
收集资料
    ↓
阅读大量文档
    ↓
提炼内容
    ↓
设计 PPT 结构
    ↓
选择模板
    ↓
寻找图片/素材
    ↓
手工排版
    ↓
调整字体、图片、图表
    ↓
检查页面
    ↓
反复修改
```

其中大量时间消耗在：

1. 阅读和理解项目资料
2. 提炼汇报逻辑
3. 确定每一页讲什么
4. 查找历史素材
5. 调整页面布局
6. 修改文字密度
7. 检查页面视觉效果

因此，本项目希望构建一个个人 PPT 智能体。

---

# 2. 项目目标

## 2.1 核心目标

构建一个：

> **能够理解个人项目资料、公司 PPT 模板、历史 PPT 和素材库，并按照用户指定页数与主题自动策划、生成和优化 PPT 的 AI Agent。**

核心流程：

```text
用户提出 PPT 需求
        ↓
分析需求
        ↓
生成 PPT 页面大纲
        ↓
用户确认 / 修改
        ↓
RAG 检索项目资料
        ↓
检索公司模板规范
        ↓
检索历史优秀页面
        ↓
选择图片/图表/素材
        ↓
生成页面设计 JSON
        ↓
PPT Renderer
        ↓
生成 PPTX
        ↓
PPT → PDF/PNG
        ↓
Vision QA
        ↓
自动修复
        ↓
最终 PPT
```

---

# 3. 核心设计原则

## 3.1 模板与素材分离

这是本系统最重要的设计原则之一。

### 公司模板负责

```text
视觉规范
页面尺寸
字体
颜色
Logo
页眉
页脚
母版
背景
常用布局
```

### 个人素材负责

```text
项目图片
系统截图
架构图
数据
图表
产品截图
现场照片
技术示意图
历史页面
```

最终关系：

```text
公司模板
     +
页面设计规则
     +
项目内容
     +
个人素材
     ↓
最终 PPT
```

不能简单理解成：

```text
上传公司模板
↓
所有页面直接复制模板
```

而应该理解成：

```text
公司模板
↓
提取 Design System
↓
允许 AI 在 Design System 范围内进行页面组合
```

---

# 4. 产品形态

系统建议设计成一个 Web 工作台。

```text
┌─────────────────────────────────────────────┐
│                 PPT AI Workspace             │
├───────────────┬─────────────────────────────┤
│               │                             │
│  项目空间      │       PPT 编辑区域          │
│               │                             │
│  华力8A       │  P1 项目背景                 │
│  应急平台      │  P2 技术架构                 │
│  年度汇报      │  P3 AI违规检测               │
│               │  P4 项目成果                 │
│               │                             │
├───────────────┼─────────────────────────────┤
│               │                             │
│  资料库        │       AI 对话区              │
│               │                             │
│  文档          │  “把第3页改成技术架构”       │
│  PPT           │  “第5页增加项目数据”         │
│  图片          │  “整体减少文字”              │
│  模板          │                             │
└───────────────┴─────────────────────────────┘
```

---

# 5. 用户核心工作流

## 5.1 创建 PPT 项目

用户输入：

```text
主题：
华力上海8A人员轨迹项目

页数：
8页

汇报对象：
公司领导

风格：
科技感、专业、简洁、高级

重点：
人员轨迹 + AI违规检测

不要重点介绍：
人员定位
```

---

# 6. 第一阶段：PPT 策划

系统不立即生成 PPT。

首先生成：

```text
P1 项目背景与建设目标

P2 洁净室人员管理痛点

P3 整体技术架构

P4 人员轨迹技术链路

P5 AI违规检测能力

P6 项目落地成果

P7 个人工作亮点

P8 项目价值与后续规划
```

用户可以：

```text
删除页面
新增页面
修改标题
调整顺序
合并页面
拆分页面
重新生成
```

例如：

```text
用户：

P3和P4合并
增加一页“AI违规检测”
P8改成“项目价值”
```

系统重新生成：

```text
P1 项目背景
P2 业务痛点
P3 技术架构与人员轨迹
P4 AI违规检测
P5 项目成果
P6 个人工作亮点
P7 项目价值
P8 后续规划
```

---

# 7. 第二阶段：页面内容策划

用户确认页面结构后，每页进入内容规划。

例如：

```text
P4 AI违规检测
```

Agent 生成：

```text
页面核心观点：

传统违规检测模型在洁净室存在较高误报，
通过真实洁净室数据训练优化模型。

核心内容：

1. 洁净室人员穿着无尘服
2. 传统模型存在误报
3. 采集真实场景数据
4. 针对洁净室场景进行模型训练
5. 建立AI违规检测能力

成果：

检测准确率约90%

建议素材：

- 未戴头盔检测截图
- 未戴口罩检测截图
- AI检测效果图
```

---

# 8. 第三阶段：RAG 检索

页面内容策划完成后，系统开始检索资料。

例如：

```text
查询：

“华力8A 洁净室 AI违规检测 准确率”
```

RAG 返回：

```text
项目技术方案
模型训练资料
测试报告
历史项目PPT
AI检测图片
```

系统从资料中提取：

```text
事实
数据
技术描述
项目成果
图片
案例
```

---

# 9. RAG 总体设计

本系统不建议只建立一个知识库。

建议设计为：

```text
                RAG Knowledge System
                         │
        ┌────────────────┼────────────────┐
        ↓                ↓                ↓
   项目知识库          公司知识库         PPT设计知识库
        │                │                │
   项目文档            公司模板          历史优秀PPT
   技术方案            品牌规范          页面案例
   测试报告            Logo              页面布局
   数据                字体              图表样式
   项目图片            配色              设计规范
```

---

# 10. 项目知识库

## 10.1 存储内容

```text
PDF
DOCX
PPTX
XLSX
TXT
Markdown
图片
架构图
CAD截图
系统截图
项目照片
测试报告
会议纪要
```

## 10.2 Metadata

每个资料必须带 Metadata。

例如：

```json
{
  "project_id": "project_hl_8a",
  "project_name": "华力上海8A人员轨迹",
  "file_id": "xxx",
  "file_name": "AI违规检测方案.pdf",
  "file_type": "pdf",
  "category": "ai_violation",
  "security_level": "confidential",
  "created_at": "2026-09-24"
}
```

---

# 11. 公司知识库

公司知识库主要保存：

```text
公司PPT模板
公司Logo
品牌规范
字体
配色
公司介绍
公司业务资料
标准页面
公司历史优秀PPT
```

例如：

```json
{
  "type": "design_rule",
  "category": "title",
  "font": "xxx",
  "font_size": 28,
  "color": "#XXXXXX"
}
```

---

# 12. PPT 设计知识库

这是本项目非常重要的一个知识库。

历史优秀 PPT 不应该只作为普通文件保存。

应该解析为：

```text
PPT
 ↓
页面
 ↓
页面类型
 ↓
布局
 ↓
元素
 ↓
视觉结构
```

例如：

```json
{
  "page_type": "kpi",
  "title_position": "top-left",
  "content_layout": "3-cards",
  "image_position": "bottom",
  "text_density": "low"
}
```

这样 AI 可以学习：

> “成果页通常怎么设计。”

而不仅仅是学习 PPT 中的文字。

---

# 13. 素材库设计

素材库与 RAG 知识库相关，但不完全相同。

建议：

```text
Asset Library
│
├── 图片
├── 图标
├── 系统截图
├── 架构图
├── 流程图
├── 数据图表
├── CAD截图
├── 产品截图
└── PPT页面
```

每个素材建立：

```json
{
  "asset_id": "asset_001",
  "project_id": "project_hl_8a",
  "type": "image",
  "category": "ai_violation",
  "tags": [
    "洁净室",
    "AI",
    "违规检测",
    "未戴头盔"
  ],
  "description": "洁净室未戴头盔检测效果截图",
  "path": "/assets/xxx.png"
}
```

---

# 14. 图片素材的 RAG

图片不能只存路径。

需要生成图片描述。

例如：

```text
图片：
20260901_no_helmet.png
```

Vision Model 自动分析：

```text
图片内容：
洁净室环境

主要对象：
人员

场景：
洁净室通道

检测内容：
未戴头盔

用途：
AI违规检测案例

适合页面：
AI能力
项目成果
技术案例
```

然后建立向量。

用户说：

> “给AI违规检测页面找一张案例图。”

系统就可以检索：

```text
AI违规检测
+
洁净室
+
未戴头盔
+
案例
```

---

# 15. 机密项目资料设计

这是系统必须重点解决的问题。

项目资料应该采用：

> **项目空间隔离 + 权限过滤 + Metadata过滤**

例如：

```text
用户
 │
 ↓
Project Context
 │
 ├── 华力8A
 │     ├── 项目资料
 │     ├── 图片
 │     └── PPT
 │
 └── 应急平台
       ├── 项目资料
       ├── 图片
       └── PPT
```

当用户在：

```text
华力8A项目
```

中生成 PPT 时：

RAG 查询必须自动附加：

```text
project_id = project_hl_8a
```

不能检索到：

```text
project_emergency
```

的资料。

---

# 16. 安全等级

建议至少：

```text
PUBLIC
INTERNAL
CONFIDENTIAL
TOP_SECRET
```

普通用户只能检索允许访问的资料。

例如：

```text
查询条件：

project_id = 当前项目
AND security_level <= 用户权限
```

---

# 17. Agent 总体架构

建议拆分为以下 Agent。

```text
                  PPT Supervisor
                        │
        ┌───────────────┼────────────────┐
        ↓               ↓                ↓
   Requirement      PPT Planner       RAG Agent
      Agent             Agent             Agent
        │               │                │
        ↓               ↓                ↓
   需求理解          页面规划          内容检索
        │               │                │
        └───────────────┼────────────────┘
                        ↓
                  Content Agent
                        ↓
                  Asset Agent
                        ↓
                  Design Agent
                        ↓
                 Renderer Agent
                        ↓
                   QA Agent
                        ↓
                Revision Agent
```

---

# 18. Supervisor Agent

Supervisor 是整个 PPT Agent 的大脑。

负责：

```text
判断当前任务
选择 Agent
控制执行顺序
管理上下文
处理用户反馈
触发重新生成
```

例如：

```text
用户：
把第5页改得更简洁。

Supervisor
 ↓
读取第5页
 ↓
调用 Design Agent
 ↓
减少文字
 ↓
调用 Renderer
 ↓
调用 QA
 ↓
返回新页面
```

---

# 19. PPT Planner Agent

负责：

```text
确定PPT结构
确定页面数量
确定页面主题
确定汇报逻辑
```

输入：

```text
主题
页数
汇报对象
使用场景
重点
限制
```

输出：

```json
{
  "pages": [
    {
      "page_no": 1,
      "title": "项目背景",
      "purpose": "解释为什么做"
    },
    {
      "page_no": 2,
      "title": "业务痛点",
      "purpose": "解释解决什么问题"
    }
  ]
}
```

---

# 20. Content Agent

负责：

```text
从RAG获取资料
提取事实
提炼核心观点
生成页面文案
```

必须遵循：

> **不能为了让 PPT 好看而编造数据。**

所有重要数据应该记录来源。

例如：

```json
{
  "content": "检测准确率约90%",
  "source": "测试报告.pdf",
  "page": 12
}
```

这样最终可以追溯：

```text
PPT内容
 ↓
数据来源
 ↓
原始文件
```

---

# 21. Asset Agent

负责选择素材。

输入：

```text
页面主题：
AI违规检测

页面类型：
案例页
```

输出：

```text
素材1：
未戴头盔检测截图

素材2：
未戴口罩检测截图

素材3：
模型检测结果截图
```

Asset Agent 不应该自己生成真实项目截图。

优先使用：

```text
用户素材
>
项目素材
>
公司素材
>
通用素材
>
AI生成素材
```

---

# 22. Design Agent

负责：

```text
选择页面类型
选择布局
确定文字数量
确定图片位置
确定数据卡片
确定视觉层级
```

例如：

```json
{
  "page_type": "case_kpi",
  "layout": "left_content_right_image",
  "title": "AI违规检测",
  "main_message": "针对洁净室场景优化违规检测模型",
  "kpi": {
    "value": "90%",
    "label": "检测准确率"
  },
  "image": {
    "asset_id": "asset_001"
  }
}
```

---

# 23. Page JSON

这是整个系统的核心中间层。

LLM 不应该直接生成 PPTX。

应该：

```text
LLM
 ↓
Page JSON
 ↓
Renderer
 ↓
PPTX
```

示例：

```json
{
  "page": {
    "width": 13.333,
    "height": 7.5,
    "template": "company_template_01",
    "layout": "two_column"
  },

  "title": {
    "text": "AI违规检测",
    "style": "title_primary"
  },

  "content": [
    {
      "type": "text",
      "title": "场景问题",
      "text": "传统模型在洁净室场景存在较高误报"
    },
    {
      "type": "text",
      "title": "解决方案",
      "text": "基于真实洁净室数据进行模型训练与优化"
    }
  ],

  "kpi": {
    "value": "90%",
    "label": "检测准确率"
  },

  "assets": [
    {
      "asset_id": "asset_001",
      "position": "right"
    }
  ]
}
```

---

# 24. 页面类型库

第一版不要支持无限布局。

建议先做 15～20 种。

```text
01 title
02 section
03 overview
04 text_image
05 two_column
06 three_column
07 architecture
08 business_flow
09 timeline
10 kpi
11 comparison
12 before_after
13 case_study
14 product_screenshot
15 chart
16 table
17 map
18 conclusion
19 summary
20 custom
```

---

# 25. 公司模板处理

公司模板 PPTX 上传后，需要进行一次解析。

解析内容：

```text
页面尺寸
母版
Layout
字体
字号
颜色
Logo
背景
页眉
页脚
占位符
常用组件
```

形成：

```text
Company Design System
```

例如：

```json
{
  "company": "company_a",
  "theme": {
    "primary_color": "#xxxxxx",
    "secondary_color": "#xxxxxx"
  },
  "font": {
    "title": "XXX",
    "body": "XXX"
  },
  "layouts": [
    "title",
    "two_column",
    "kpi",
    "architecture"
  ]
}
```

---

# 26. 模板与页面布局的关系

建议：

```text
公司模板
     ↓
Design System
     ↓
Page Template
     ↓
Page JSON
     ↓
Renderer
```

而不是：

```text
公司模板
 ↓
复制一页
 ↓
把所有内容塞进去
```

这样才能保证不同页面之间既统一又不会千篇一律。

---

# 27. PPT Renderer

推荐：

```text
Node.js
+
PptxGenJS
```

原因：

* PPT生成成熟
* 图形支持较好
* 文本支持较好
* 图片支持方便
* 图表支持
* 适合模板化生成
* 方便建立页面组件库

---

# 28. Renderer 组件系统

不要让 Renderer 直接处理大量底层坐标。

应该建立组件：

```text
PptComponent
│
├── Title
├── Subtitle
├── TextBlock
├── Image
├── KPI
├── Card
├── Table
├── Chart
├── Timeline
├── Flow
├── Architecture
├── Badge
└── Footer
```

例如：

```javascript
addTitle(slide, config);

addKpiCard(slide, config);

addImage(slide, config);

addTextBlock(slide, config);
```

---

# 29. Layout Engine

页面布局建议采用相对坐标。

例如：

```text
页面：
13.333 × 7.5

Grid：
12列

Margin：
0.5

Gutter：
0.2
```

页面元素使用：

```text
column
row
width
height
```

而不是大量硬编码：

```text
x = 4.137
y = 2.871
```

这样后期调整布局更加容易。

---

# 30. PPT 生成流程

```text
Page JSON
    ↓
读取 Company Design System
    ↓
读取 Page Template
    ↓
加载 Assets
    ↓
Layout Engine
    ↓
Renderer
    ↓
PPTX
```

---

# 31. 视觉 QA

生成 PPT 后，不应该直接交付。

需要：

```text
PPTX
 ↓
LibreOffice
 ↓
PDF
 ↓
PNG
 ↓
Vision Model
```

每页进行视觉检查。

---

# 32. Vision QA 检查项

## 32.1 几何问题

```text
文字溢出
元素重叠
图片超出边界
图片变形
元素未对齐
```

## 32.2 视觉问题

```text
文字过密
字号过小
留白不足
页面失衡
重点不突出
图片太小
```

## 32.3 内容问题

```text
标题与内容不一致
数据缺少单位
文字重复
页面逻辑不清晰
```

---

# 33. QA 输出

例如：

```json
{
  "page": 5,
  "status": "warning",
  "issues": [
    {
      "type": "text_density",
      "severity": "high",
      "message": "右侧正文内容过多"
    },
    {
      "type": "image_size",
      "severity": "medium",
      "message": "案例图片占比不足"
    }
  ]
}
```

---

# 34. 自动修复

QA 发现问题：

```text
第5页文字太多
```

Revision Agent：

```text
减少正文30%
保留核心观点
保留90% KPI
扩大案例图片
```

重新：

```text
Page JSON
 ↓
Renderer
 ↓
QA
```

直到：

```text
PASS
```

或者达到最大迭代次数。

建议：

```text
最大自动迭代次数 = 3
```

---

# 35. DeepSeek Harness 在系统中的位置

建议将 Harness 作为：

> Agent Runtime / Orchestrator

负责：

```text
Agent调用
Tool调用
任务状态
上下文
Workflow
错误处理
多步骤执行
```

整体：

```text
DeepSeek Harness
       │
       ├── Requirement Agent
       ├── Planner Agent
       ├── RAG Agent
       ├── Content Agent
       ├── Asset Agent
       ├── Design Agent
       ├── Renderer Agent
       └── QA Agent
```

---

# 36. Tool 系统

Agent 不应该直接访问所有系统。

应该通过 Tool。

例如：

```text
search_documents()
search_assets()
get_project()
get_template()
get_design_system()
read_document()
read_ppt()
get_image()
create_page()
render_ppt()
render_page()
check_page()
```

---

# 37. 推荐 Tool 列表

```text
File Tools
├── list_files
├── search_files
├── read_file
└── get_file_metadata

RAG Tools
├── semantic_search
├── hybrid_search
├── search_by_project
└── search_by_category

Asset Tools
├── search_assets
├── get_asset
└── recommend_assets

PPT Tools
├── create_outline
├── create_page
├── render_page
├── render_ppt
└── export_pdf

QA Tools
├── inspect_page
├── inspect_ppt
└── auto_fix
```

---

# 38. 技术栈

推荐第一版：

```text
Frontend
    Next.js / React

Agent
    Python

Agent Runtime
    DeepSeek Harness

LLM
    DeepSeek
    可扩展其他模型

Embedding
    支持本地Embedding模型

RAG
    PostgreSQL + pgvector
    或 Milvus

Backend
    Python FastAPI

PPT Renderer
    Node.js + PptxGenJS

Document Parser
    Python

PDF
    PyMuPDF

DOCX
    python-docx

PPTX
    python-pptx / OOXML

XLSX
    openpyxl

Image
    Pillow

OCR
    PaddleOCR / 其他OCR

Vision
    多模态模型

Rendering
    LibreOffice

Object Storage
    MinIO

Database
    PostgreSQL
```

---

# 39. 为什么 Agent 核心不建议 Java

虽然现有业务系统使用 Java Spring Boot，但 PPT Agent 本身更适合 Python。

原因：

```text
Python
│
├── LLM
├── Agent
├── RAG
├── Embedding
├── OCR
├── Vision
├── PDF
├── PPT
├── 数据分析
└── AI生态
```

成熟度更高。

如果后续需要接入现有 Java 平台，可以：

```text
Java业务系统
      ↓
HTTP API
      ↓
PPT AI Service
      ↓
Python
```

---

# 40. Java 与 Python 的边界

如果公司已有：

```text
Spring Cloud
MySQL
Redis
MinIO
```

可以继续使用。

架构：

```text
                  Spring Cloud
                       │
                 PPT AI Gateway
                       │
                       ↓
                 Python AI Service
                       │
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
       RAG           Agent          PPT
        │              │             │
        └──────────────┼──────────────┘
                       ↓
                     MinIO
```

---

# 41. 数据库设计

建议 PostgreSQL 作为 AI 系统数据库。

## 41.1 project

```sql
CREATE TABLE ppt_project (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    template_id BIGINT,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

---

# 42. document

```sql
CREATE TABLE ppt_document (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(32),
    storage_path TEXT,
    security_level VARCHAR(32),
    status VARCHAR(32),
    created_at TIMESTAMP NOT NULL
);
```

---

# 43. document_chunk

```sql
CREATE TABLE ppt_document_chunk (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL,
    content TEXT NOT NULL,
    page_no INT,
    chunk_index INT,
    metadata JSONB,
    embedding VECTOR(1536)
);
```

实际 embedding 维度根据模型确定。

---

# 44. asset

```sql
CREATE TABLE ppt_asset (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT,
    asset_type VARCHAR(32),
    file_name VARCHAR(255),
    storage_path TEXT,
    description TEXT,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL
);
```

---

# 45. ppt_template

```sql
CREATE TABLE ppt_template (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    file_path TEXT,
    version VARCHAR(32),
    status VARCHAR(32),
    created_at TIMESTAMP NOT NULL
);
```

---

# 46. design_system

```sql
CREATE TABLE ppt_design_system (
    id BIGSERIAL PRIMARY KEY,
    template_id BIGINT NOT NULL,
    design_json JSONB NOT NULL,
    version VARCHAR(32),
    created_at TIMESTAMP NOT NULL
);
```

---

# 47. ppt_document_instance

用于保存一次生成任务。

```sql
CREATE TABLE ppt_document_instance (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT,
    title VARCHAR(255),
    page_count INT,
    status VARCHAR(32),
    ppt_path TEXT,
    pdf_path TEXT,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

---

# 48. ppt_page

```sql
CREATE TABLE ppt_page (
    id BIGSERIAL PRIMARY KEY,
    ppt_id BIGINT NOT NULL,
    page_no INT NOT NULL,
    title VARCHAR(255),
    page_type VARCHAR(64),
    page_json JSONB,
    status VARCHAR(32),
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

---

# 49. PPT生成状态

```text
DRAFT
 ↓
OUTLINE_GENERATED
 ↓
OUTLINE_CONFIRMED
 ↓
CONTENT_GENERATED
 ↓
DESIGN_GENERATED
 ↓
RENDERING
 ↓
QA
 ↓
REVISION
 ↓
COMPLETED
```

---

# 50. API设计

## 创建项目

```http
POST /api/ppt/projects
```

## 上传资料

```http
POST /api/ppt/projects/{projectId}/documents
```

## 上传素材

```http
POST /api/ppt/projects/{projectId}/assets
```

## 上传模板

```http
POST /api/ppt/templates
```

## 创建 PPT

```http
POST /api/ppt/documents
```

请求：

```json
{
  "projectId": 1001,
  "title": "华力8A人员轨迹项目",
  "pageCount": 8,
  "audience": "领导",
  "style": "科技感、专业、简洁",
  "requirements": [
    "突出人员轨迹",
    "突出AI违规检测"
  ]
}
```

---

# 51. 生成大纲

```http
POST /api/ppt/documents/{id}/outline/generate
```

返回：

```json
{
  "pages": [
    {
      "pageNo": 1,
      "title": "项目背景",
      "purpose": "说明项目建设背景"
    }
  ]
}
```

---

# 52. 确认大纲

```http
POST /api/ppt/documents/{id}/outline/confirm
```

---

# 53. 生成页面

```http
POST /api/ppt/documents/{id}/pages/{pageNo}/generate
```

---

# 54. 修改页面

例如：

```text
POST /api/ppt/documents/{id}/pages/5/chat
```

请求：

```json
{
  "message": "第5页文字太多，减少一半，并突出90%这个数据"
}
```

---

# 55. 生成最终 PPT

```http
POST /api/ppt/documents/{id}/render
```

---

# 56. QA

```http
POST /api/ppt/documents/{id}/qa
```

---

# 57. 文件存储

建议 MinIO：

```text
ppt/
├── templates/
├── projects/
│   ├── hl-8a/
│   │   ├── documents/
│   │   ├── assets/
│   │   ├── generated/
│   │   └── previews/
│   └── emergency/
│       ├── documents/
│       ├── assets/
│       ├── generated/
│       └── previews/
```

---

# 58. 文档处理流程

上传 PDF：

```text
PDF
 ↓
解析页面
 ↓
提取文本
 ↓
提取图片
 ↓
OCR
 ↓
Chunk
 ↓
Metadata
 ↓
Embedding
 ↓
Vector DB
```

---

# 59. PPT 处理流程

```text
PPTX
 ↓
解析Slide
 ↓
解析文本
 ↓
解析图片
 ↓
解析Shape
 ↓
解析Layout
 ↓
提取页面截图
 ↓
Vision分析
 ↓
生成Page Design Metadata
 ↓
进入PPT Design RAG
```

---

# 60. RAG 检索策略

不建议只做向量搜索。

推荐：

```text
Hybrid Search
```

即：

```text
关键词检索
+
向量检索
+
Metadata过滤
```

例如：

```text
query：

“洁净室 AI违规检测”

Metadata：

project_id = hl_8a
category = ai_violation
security_level = confidential
```

---

# 61. RAG 检索优先级

建议：

```text
当前项目资料
    ↓
当前项目历史PPT
    ↓
公司知识库
    ↓
个人通用知识
```

不要反过来。

---

# 62. RAG Context 组装

最终交给 LLM 的 Context：

```text
用户需求
+
页面主题
+
项目资料
+
公司设计规范
+
历史页面案例
+
素材候选
```

例如：

```text
[用户需求]
制作华力8A AI违规检测页面

[项目事实]
...

[历史PPT案例]
...

[公司设计规范]
...

[推荐素材]
...

[页面类型]
case_kpi
```

---

# 63. 防止 AI 幻觉

所有项目数据必须：

```text
事实
 ↓
来源
 ↓
可信度
```

例如：

```json
{
  "statement": "检测准确率约90%",
  "source_document": "AI测试报告.pdf",
  "source_page": 12
}
```

如果 RAG 找不到数据：

```text
不要自动生成。
```

应该提示：

> 当前资料中未找到该数据，是否使用用户提供的数据？

---

# 64. PPT 内容质量规则

每页建议只有：

```text
1个核心观点
+
2～4个支撑点
+
1～2个视觉元素
```

避免：

```text
一页放十几个观点
```

---

# 65. 文字密度规则

建议设计：

```text
标题：
20～32pt

正文：
16～22pt

辅助说明：
12～16pt
```

具体数值以公司模板为准。

系统需要在 QA 阶段检查：

```text
字体过小
文字过多
文本框过长
```

---

# 66. 页面设计规则

例如：

## 技术架构页

```text
标题
 ↓
架构图
 ↓
关键说明
```

## KPI页

```text
标题

90%      40路       22台
准确率    摄像头     测试点

说明
```

## 对比页

```text
方案A          方案B

原理           原理
优点           优点
局限           局限
适用场景       适用场景
```

---

# 67. 用户交互设计

最核心的不是：

> “生成 PPT”

而是：

> **“与 AI 一起做 PPT。”**

用户可以直接说：

```text
把第3页改成架构图
```

```text
第4页文字太多
```

```text
这张图片不要
```

```text
把这个数据做成大数字
```

```text
所有页面更加高级一点
```

```text
保持公司模板，不要改变颜色
```

Agent 根据当前 PPT 状态进行修改。

---

# 68. PPT 状态管理

每个页面都应该有独立版本。

例如：

```text
P5
 ├── v1
 ├── v2
 ├── v3
 └── current
```

用户可以：

```text
恢复上一版本
```

---

# 69. 页面级生成

不要每次修改一页都重新生成整个 PPT。

例如：

```text
修改P5
 ↓
只重新生成P5
 ↓
重新渲染
 ↓
QA
```

最终再：

```text
Render All
```

---

# 70. MVP 第一阶段

第一版只实现：

```text
1. 创建项目

2. 上传资料

3. 上传公司模板

4. RAG

5. 生成PPT大纲

6. 用户确认大纲

7. 生成页面内容

8. 选择素材

9. Page JSON

10. PPTX生成

11. PDF预览

12. 基础视觉QA
```

---

# 71. MVP 第一阶段不做

暂时不做：

```text
复杂动画
实时多人协作
在线PPT编辑器
复杂3D
复杂视频
自动生成所有类型图表
复杂CAD解析
全自动艺术设计
```

先把：

> **内容正确 + 页面好看 + 模板统一**

做好。

---

# 72. V2

第二阶段：

```text
历史PPT学习
页面设计RAG
图片智能检索
自动图表
自动流程图
自动架构图
Vision QA
自动修复
```

---

# 73. V3

第三阶段：

```text
个人风格学习
公司风格学习
自动优化汇报逻辑
跨项目知识库
PPT质量评分
一键生成多个版本
```

例如：

```text
领导版
技术版
客户版
销售版
员工述职版
```

同一套项目资料自动生成不同版本。

---

# 74. V4

最终可以演进为：

```text
Personal Presentation Agent
```

不仅生成 PPT：

```text
项目资料
 ↓
分析
 ↓
PPT
 ↓
汇报稿
 ↓
演讲稿
 ↓
Q&A
 ↓
领导可能提问
 ↓
回答建议
```

例如：

```text
PPT第5页：
AI违规检测

AI同时生成：

这一页怎么讲：
“这里重点想说明的是……”

领导可能问：
“90%准确率怎么计算？”

建议回答：
……
```

---

# 75. 项目目录

推荐：

```text
ppt-agent/
│
├── apps/
│   ├── web/
│   │   └── frontend
│   │
│   ├── agent/
│   │   ├── agents/
│   │   │   ├── supervisor/
│   │   │   ├── planner/
│   │   │   ├── content/
│   │   │   ├── asset/
│   │   │   ├── design/
│   │   │   └── qa/
│   │   │
│   │   ├── tools/
│   │   ├── workflows/
│   │   └── prompts/
│   │
│   ├── rag/
│   │   ├── ingestion/
│   │   ├── retrieval/
│   │   ├── embedding/
│   │   └── metadata/
│   │
│   ├── document-parser/
│   │   ├── pdf/
│   │   ├── pptx/
│   │   ├── docx/
│   │   └── xlsx/
│   │
│   ├── ppt-renderer/
│   │   ├── components/
│   │   ├── layouts/
│   │   ├── templates/
│   │   └── renderer/
│   │
│   └── vision-qa/
│       ├── render/
│       ├── analyze/
│       └── repair/
│
├── packages/
│   ├── schemas/
│   └── common/
│
├── deploy/
│   ├── docker/
│   └── compose/
│
├── docs/
│   ├── architecture.md
│   ├── rag.md
│   ├── ppt-renderer.md
│   └── agent.md
│
└── README.md
```

---

# 76. Prompt 管理

Prompt 不建议散落在代码中。

统一：

```text
prompts/
├── supervisor/
├── planner/
├── content/
├── asset/
├── design/
├── qa/
└── revision/
```

例如：

```text
design_page_v1.md
design_page_v2.md
```

方便版本管理。

---

# 77. Agent 上下文设计

不要把整个项目所有资料塞给 Agent。

采用：

```text
Global Context
+
Project Context
+
Page Context
+
Retrieved Context
```

例如：

```text
Global：
公司PPT规范

Project：
华力8A

Page：
AI违规检测

Retrieved：
AI测试报告
AI截图
历史PPT页面
```

---

# 78. Token 控制

RAG 不应该：

```text
检索100个文档
全部给LLM
```

建议：

```text
Top K = 5～10
```

然后：

```text
Reranker
 ↓
Top 3～5
 ↓
LLM
```

---

# 79. 数据来源优先级

建议：

```text
当前项目原始资料
        ↓
项目历史PPT
        ↓
公司标准资料
        ↓
个人历史资料
        ↓
通用知识
```

---

# 80. 模板约束机制

必须明确：

```text
AI允许：
✓ 修改文字
✓ 更换图片
✓ 调整布局
✓ 调整元素数量
✓ 选择页面类型

AI不允许：
✗ 修改公司Logo
✗ 随意修改品牌色
✗ 修改公司字体规范
✗ 使用未授权素材
✗ 跨项目读取机密资料
```

---

# 81. 素材选择策略

推荐评分：

```text
素材相关性
+
项目相关性
+
页面适配度
+
图片质量
+
历史使用效果
```

例如：

```text
Asset Score

0.35 × semantic_similarity
+
0.25 × project_match
+
0.20 × page_type_match
+
0.10 × image_quality
+
0.10 × historical_usage
```

第一版可以简化，不必一开始实现复杂算法。

---

# 82. PPT 生成质量指标

系统最终需要建立质量指标。

## 内容质量

```text
事实准确率
数据可追溯率
RAG命中率
```

## 页面质量

```text
文本溢出率
元素重叠率
图片变形率
```

## 视觉质量

```text
字体一致性
颜色一致性
页面密度
视觉平衡
```

## 用户体验

```text
生成时间
修改次数
用户接受率
```

---

# 83. 最终系统架构

```text
                              用户
                               │
                               ↓
                    ┌──────────────────┐
                    │   PPT Workspace  │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ DeepSeek Harness │
                    │ Agent Runtime    │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ Supervisor Agent │
                    └────────┬─────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ↓                    ↓                    ↓
   Planner Agent        RAG Agent           Asset Agent
        │                    │                    │
        ↓                    ↓                    ↓
    页面规划              项目资料              素材检索
                             │
                             ↓
                     Content Agent
                             │
                             ↓
                      Design Agent
                             │
                             ↓
                       Page JSON
                             │
                             ↓
                    Node.js Renderer
                       PptxGenJS
                             │
                             ↓
                           PPTX
                             │
                             ↓
                        LibreOffice
                             │
                             ↓
                       PDF / PNG
                             │
                             ↓
                       Vision QA
                             │
                    ┌────────┴────────┐
                    ↓                 ↓
                  PASS              FAIL
                    │                 │
                    ↓                 ↓
                  完成          Revision Agent
                                      │
                                      ↓
                                  Page JSON
```

---

# 84. 第一版开发优先级

建议严格按照下面顺序开发。

```text
Phase 1
项目空间
文件上传
MinIO
基础数据库

Phase 2
PDF/PPT/DOCX解析
文本Chunk
Embedding
RAG

Phase 3
公司模板解析
Design System

Phase 4
PPT Planner
页面大纲
用户确认

Phase 5
Content Agent
Asset Agent

Phase 6
Page JSON
PPT Renderer

Phase 7
PPT预览
PDF/PNG

Phase 8
Vision QA

Phase 9
自动修复

Phase 10
历史PPT设计RAG
```

---

# 85. MVP 成功标准

第一版不要以：

> “能不能一键生成 PPT”

作为唯一标准。

应该定义为：

### 输入

```text
1个公司模板
+
1个项目资料库
+
8页PPT需求
```

### 输出

```text
8页PPT
```

并且：

```text
✓ 使用公司模板风格
✓ 内容来自项目资料
✓ 数据可追溯
✓ 能选择项目素材
✓ 页面不存在明显重叠
✓ 页面不存在严重文字溢出
✓ 字体基本统一
✓ 页面风格统一
✓ 用户可以逐页修改
✓ 可以重新生成单页
```

达到这个标准，MVP 就成功。

---

# 86. 最终产品定位

最终这个项目不应该只是：

> AI PPT生成器

而应该是：

> **个人 PPT 智能工作台**

核心能力：

```text
我的项目资料
        +
公司的PPT规范
        +
我的历史PPT
        +
我的素材库
        +
AI策划能力
        +
AI设计能力
        +
AI生成能力
        +
AI视觉检查
```

最终形成：

```text
                我的 PPT Agent
                       │
       ┌───────────────┼───────────────┐
       ↓               ↓               ↓
   知识资产          设计资产          生成能力
       │               │               │
   项目资料          公司模板          PPT
   技术方案          页面案例          汇报稿
   项目数据          视觉规范          演讲稿
   项目图片          个人风格          Q&A
```

---

# 87. 最终建议

整个项目最重要的不是“大模型有多强”，而是下面这条链路：

```text
资料
 ↓
RAG
 ↓
理解项目
 ↓
理解汇报目标
 ↓
策划页面
 ↓
选择设计
 ↓
选择素材
 ↓
生成Page JSON
 ↓
Renderer
 ↓
视觉检查
 ↓
自动修改
```

其中：

```text
DeepSeek Harness
```

负责 **Agent 编排**；

```text
RAG
```

负责 **“知道项目是什么”**；

```text
Design System
```

负责 **“知道公司PPT应该长什么样”**；

```text
Asset RAG
```

负责 **“知道应该用什么素材”**；

```text
Page JSON
```

负责 **“把AI想法结构化”**；

```text
PptxGenJS
```

负责 **“真正把页面画出来”**；

```text
Vision QA
```

负责 **“判断生成出来的PPT到底好不好”**。

最终形成一个闭环：

```text
        ┌───────────────────────────┐
        │                           │
        ↓                           │
用户需求 → 策划 → RAG → 设计 → 生成 │
                             ↓      │
                            QA      │
                             ↓      │
                          自动修复 ──┘
```

这套架构能够支撑从第一版 MVP 一直演进到真正的个人 PPT 智能体，而不需要后期推翻重做。
