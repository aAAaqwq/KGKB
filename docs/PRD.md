# Knowledge Graph KB — 产品需求文档 (PRD)

> **项目代号**: KGKB  
> **优先级**: P0 战略级  
> **立项人**: Daniel Li  
> **编写人**: 小pm (CPO)  
> **创建日期**: 2026-03-16  
> **目标交付**: 2周 MVP  

---

## 1. 项目愿景与定位

### 1.1 一句话定位
**基于图谱可视化的可预测关联万物的知识库** — 一个让知识可见、可关联、可预测的下一代知识管理系统。

### 1.2 项目愿景
让每个人都能拥有一个"第二大脑"，不仅能存储和检索知识，还能通过图谱可视化发现知识之间的隐藏关联，并通过AI预测未来趋势。

### 1.3 核心价值主张

| 维度 | 价值 |
|------|------|
| **存储** | 本地优先，数据主权在用户手中 |
| **可视化** | 知识图谱直观展示，发现隐藏关联 |
| **预测** | AI驱动的趋势预测，辅助决策 |
| **开放** | 开源免费，可自托管，可扩展 |
| **集成** | 与OpenClaw等AI agent无缝对接 |

### 1.4 目标用户

| 用户类型 | 痛点 | 核心需求 |
|----------|------|----------|
| **知识工作者** | 知识碎片化，难以关联 | 统一存储 + 图谱关联 |
| **研究人员** | 文献多，关系复杂 | 可视化 + 趋势预测 |
| **AI开发者** | 需要本地知识库 | 向量化 + API集成 |
| **内容创作者** | 灵感零散，难以串联 | 知识图谱 + 创意预测 |

### 1.5 与现有方案对比

| 维度 | Notion/Obsidian | QMD | GitNexus | MiroFish | **KGKB (本项目)** |
|------|-----------------|-----|----------|----------|-------------------|
| 本地存储 | ⚠️ 云端为主 | ✅ | ✅ | ✅ | ✅ |
| 图谱可视化 | ⚠️ 插件 | ❌ | ✅ | ❌ | ✅ |
| AI预测 | ❌ | ❌ | ❌ | ✅ | ✅ |
| 向量化 | ❌ | ✅ | ✅ | ❌ | ✅ |
| CLI支持 | ❌ | ✅ | ❌ | ❌ | ✅ |
| AI Agent集成 | ❌ | ⚠️ OpenClaw | ❌ | ❌ | ✅ |

---

## 2. 核心功能列表

### 2.1 功能优先级矩阵

| 优先级 | 功能模块 | 说明 | MVP |
|:------:|----------|------|:---:|
| **P0** | 知识存储（CLI） | 命令行添加/查询知识 | ✅ |
| **P0** | 向量化引擎 | 调用外部API进行embedding | ✅ |
| **P0** | 图谱可视化 | Web界面展示知识节点和关系 | ✅ |
| **P0** | 基础关联 | 手动建立知识关联 | ✅ |
| **P1** | 知识存储（WebUI） | Web界面添加/编辑知识 | ✅ |
| **P1** | 自动关联 | AI自动发现知识关联 | ❌ |
| **P1** | OpenClaw集成 | 作为OpenClaw知识库 | ❌ |
| **P1** | 基础预测 | 基于图谱的简单趋势预测 | ❌ |
| **P2** | 高级预测 | 多Agent模拟预测 | ❌ |
| **P2** | 协作功能 | 多用户协作 | ❌ |
| **P2** | 插件系统 | 自定义扩展 | ❌ |

### 2.2 P0 功能详解

#### F1: 知识存储（CLI）
```
kgkb add "知识内容" --tags "tag1,tag2" --source "url"
kgkb query "搜索关键词" --limit 10
kgkb list --tag "tag1"
kgkb export --format json
```

**验收标准**:
- [ ] 支持文本、URL、Markdown三种输入格式
- [ ] 支持标签分类
- [ ] 支持元数据（来源、时间、作者）
- [ ] 存储到本地SQLite

#### F2: 向量化引擎
```
kgkb embed --provider openai --model text-embedding-3-small
kgkb embed --provider ollama --model nomic-embed-text
kgkb embed --provider custom --endpoint http://localhost:8080/embed
```

**验收标准**:
- [ ] 支持OpenAI embedding API
- [ ] 支持Ollama本地embedding
- [ ] 支持自定义API endpoint
- [ ] 向量存储到FAISS/ChromaDB

#### F3: 图谱可视化（WebUI）
- 节点：每个知识点是一个节点
- 边：知识之间的关联关系
- 交互：拖拽、缩放、点击查看详情

**验收标准**:
- [ ] 使用D3.js或Cytoscape.js渲染图谱
- [ ] 支持节点拖拽和缩放
- [ ] 点击节点显示详情
- [ ] 支持按标签筛选显示

#### F4: 基础关联
```
kgkb link <node1_id> <node2_id> --relation "相关"
kgkb unlink <node1_id> <node2_id>
kgkb relations <node_id>
```

**验收标准**:
- [ ] 支持手动创建关联
- [ ] 支持定义关联类型（相关、因果、包含等）
- [ ] 关联在图谱中可视化显示

### 2.3 P1 功能详解

#### F5: 知识存储（WebUI）
- 表单添加知识
- Markdown编辑器
- 批量导入（CSV/JSON）

#### F6: 自动关联
- AI分析知识内容
- 自动发现语义相似的知识
- 推荐关联关系

#### F7: OpenClaw集成
- 提供标准API供OpenClaw调用
- 支持知识检索和向量检索
- 作为OpenClaw Skill集成

#### F8: 基础预测
- 基于知识图谱分析趋势
- 预测知识节点的重要性变化
- 推荐值得关注的知识领域

---

## 3. 技术架构概述

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                           KGKB System                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │   CLI Layer  │    │  WebUI Layer │    │   API Layer          │  │
│  │  (kgkb CLI)  │    │  (React SPA) │    │   (REST API)         │  │
│  └──────┬───────┘    └──────┬───────┘    └──────────┬───────────┘  │
│         │                   │                       │               │
│         └───────────────────┴───────────────────────┘               │
│                             │                                        │
│                    ┌────────┴────────┐                              │
│                    │   Core Engine   │                              │
│                    │   (FastAPI)     │                              │
│                    └────────┬────────┘                              │
│                             │                                        │
│         ┌───────────────────┼───────────────────┐                   │
│         │                   │                   │                    │
│  ┌──────┴──────┐    ┌──────┴──────┐    ┌──────┴──────┐            │
│  │  Knowledge  │    │   Vector    │    │    Graph    │            │
│  │   Store     │    │   Engine    │    │   Engine    │            │
│  │  (SQLite)   │    │ (FAISS/     │    │ (NetworkX)  │            │
│  │             │    │  ChromaDB)  │    │             │            │
│  └─────────────┘    └─────────────┘    └─────────────┘            │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    External Integrations                       │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐  │  │
│  │  │ OpenAI  │  │ Ollama  │  │ Custom  │  │    OpenClaw     │  │  │
│  │  │   API   │  │  Local  │  │   API   │  │    Integration  │  │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 技术栈选型

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| **CLI** | Python + Click/Typer | 命令行工具 |
| **WebUI** | React + TypeScript | 现代前端框架 |
| **图谱可视化** | D3.js / Cytoscape.js | 图谱渲染 |
| **API** | FastAPI | 高性能Python API框架 |
| **知识存储** | SQLite | 轻量级本地数据库 |
| **向量存储** | FAISS / ChromaDB | 向量相似度检索 |
| **图引擎** | NetworkX | 图计算和分析 |
| **Embedding** | OpenAI API / Ollama | 向量化服务 |

### 3.3 数据模型

```sql
-- 知识节点
CREATE TABLE knowledge_nodes (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    content_type TEXT DEFAULT 'text',  -- text, url, markdown
    title TEXT,
    tags TEXT,  -- JSON array
    metadata TEXT,  -- JSON object
    embedding_id TEXT,  -- 关联向量ID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 知识关联
CREATE TABLE knowledge_relations (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation_type TEXT DEFAULT 'related',  -- related, causes, contains, etc.
    weight REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES knowledge_nodes(id),
    FOREIGN KEY (target_id) REFERENCES knowledge_nodes(id)
);

-- 向量索引（FAISS管理，元数据存储）
CREATE TABLE embeddings (
    id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    provider TEXT,  -- openai, ollama, custom
    model TEXT,
    dimension INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (node_id) REFERENCES knowledge_nodes(id)
);
```

### 3.4 API 设计

#### 核心API端点

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/knowledge` | 添加知识 |
| GET | `/api/knowledge/{id}` | 获取知识详情 |
| PUT | `/api/knowledge/{id}` | 更新知识 |
| DELETE | `/api/knowledge/{id}` | 删除知识 |
| GET | `/api/knowledge/search` | 搜索知识 |
| POST | `/api/knowledge/{id}/embed` | 向量化知识 |
| POST | `/api/relations` | 创建关联 |
| GET | `/api/graph` | 获取图谱数据 |
| GET | `/api/graph/node/{id}` | 获取节点及其关联 |

---

## 4. MVP 范围（2周交付）

### 4.1 MVP 目标
**2周内交付一个可用的知识图谱知识库原型**，支持CLI存入、WebUI可视化、基础关联。

### 4.2 MVP 功能清单

| 功能 | 完成标准 | 工时估算 |
|------|----------|:--------:|
| CLI核心命令 | add/query/list/export 可用 | 2天 |
| SQLite存储 | 数据模型+CRUD | 1天 |
| 向量化集成 | OpenAI/Ollama可用 | 2天 |
| FastAPI后端 | 核心API可用 | 2天 |
| WebUI框架 | React项目搭建 | 1天 |
| 图谱可视化 | D3.js基础渲染 | 3天 |
| 关联功能 | 手动创建关联 | 1天 |

**总计**: 约12人天，2周内可完成

### 4.3 MVP 排除项

| 排除功能 | 原因 | 计划版本 |
|----------|------|----------|
| 自动关联 | 技术复杂度高 | v1.1 |
| AI预测 | 需要更多数据 | v1.2 |
| OpenClaw集成 | 依赖API稳定 | v1.1 |
| 多用户协作 | 架构改动大 | v2.0 |
| 插件系统 | 优先级低 | v2.0 |

### 4.4 MVP 交付物

```
knowledge-graph-kb/
├── kgkb/                    # Python包
│   ├── cli.py              # CLI入口
│   ├── api/                # FastAPI后端
│   ├── core/               # 核心引擎
│   │   ├── storage.py      # SQLite存储
│   │   ├── embedding.py    # 向量化引擎
│   │   └── graph.py        # 图引擎
│   └── models/             # 数据模型
├── webui/                   # React前端
│   ├── src/
│   │   ├── components/
│   │   │   └── Graph/      # 图谱组件
│   │   └── pages/
│   └── package.json
├── docs/                    # 文档
│   ├── getting-started.md
│   └── api-reference.md
├── tests/                   # 测试
├── requirements.txt
└── README.md
```

---

## 5. 用户故事

### 5.1 核心用户故事

#### US1: CLI快速存入知识
> 作为知识工作者，我希望通过命令行快速存入知识，以便高效管理我的知识库。

**验收标准**:
- Given 我有一条知识要存入
- When 我执行 `kgkb add "知识内容" --tags "tag1"`
- Then 知识被存储到本地数据库，并返回知识ID

#### US2: 图谱可视化浏览
> 作为研究人员，我希望在Web界面看到知识的图谱视图，以便发现知识之间的关联。

**验收标准**:
- Given 我的知识库有多个知识点和关联
- When 我打开WebUI图谱页面
- Then 我看到所有知识点作为节点，关联作为边，可以拖拽和缩放

#### US3: 向量化检索
> 作为AI开发者，我希望知识被向量化存储，以便进行语义相似度检索。

**验收标准**:
- Given 我有向量化后的知识库
- When 我执行 `kgkb query "相关概念" --semantic`
- Then 返回语义最相似的知识列表

#### US4: 手动建立关联
> 作为内容创作者，我希望手动建立知识之间的关联，以便构建我的知识网络。

**验收标准**:
- Given 我有两个相关的知识点
- When 我执行 `kgkb link <id1> <id2> --relation "相关"`
- Then 两个知识点建立了关联，并在图谱中显示

#### US5: OpenClaw集成（P1）
> 作为OpenClaw用户，我希望KGKB作为我的知识库后端，以便AI agent检索我的知识。

**验收标准**:
- Given OpenClaw配置了KGKB作为知识库
- When AI agent执行知识检索
- Then 返回相关的知识内容

---

## 6. 成功指标

### 6.1 MVP 成功指标（2周）

| 指标 | 目标 | 衡量方式 |
|------|------|----------|
| **功能完整性** | MVP功能100%完成 | 功能测试通过率 |
| **CLI可用性** | 5个核心命令可用 | CLI测试覆盖 |
| **WebUI可用性** | 图谱可渲染100+节点 | 性能测试 |
| **向量化准确率** | 语义检索准确率>80% | 人工评测 |
| **文档完整性** | README + API文档 | 文档审查 |

### 6.2 长期成功指标（6个月）

| 指标 | 目标 | 衡量方式 |
|------|------|----------|
| **GitHub Stars** | 1000+ | GitHub统计 |
| **周活跃用户** | 100+ | 使用统计 |
| **知识存储量** | 平均1000条/用户 | 数据库统计 |
| **预测准确率** | >70%（可验证场景）| A/B测试 |

---

## 7. 里程碑计划

### 7.1 MVP 里程碑（2周）

```
Week 1: 核心功能
├── Day 1-2: 项目初始化 + CLI核心命令
│   ├── 项目结构搭建
│   ├── SQLite数据模型
│   └── CLI add/query/list实现
├── Day 3-4: 向量化引擎
│   ├── OpenAI embedding集成
│   ├── Ollama embedding集成
│   └── 向量存储（FAISS）
└── Day 5: FastAPI后端
    ├── 核心API实现
    └── API文档

Week 2: WebUI + 集成
├── Day 6-7: WebUI框架
│   ├── React项目搭建
│   ├── 基础页面布局
│   └── API集成
├── Day 8-10: 图谱可视化
│   ├── D3.js集成
│   ├── 节点/边渲染
│   └── 交互功能（拖拽/缩放/点击）
├── Day 11: 关联功能
│   ├── CLI关联命令
│   └── 图谱关联显示
└── Day 12-14: 收尾
    ├── 测试 + Bug修复
    ├── 文档完善
    └── MVP发布
```

### 7.2 后续版本规划

| 版本 | 时间 | 核心功能 |
|------|------|----------|
| **v1.0 MVP** | 2周 | CLI + 图谱可视化 + 基础关联 |
| **v1.1** | +2周 | WebUI存入 + 自动关联 + OpenClaw集成 |
| **v1.2** | +2周 | AI预测 + 高级分析 |
| **v2.0** | +4周 | 多用户协作 + 插件系统 |

### 7.3 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|:----:|:----:|----------|
| 图谱性能问题（节点过多） | 中 | 高 | 实现懒加载/分页渲染 |
| 向量化API不稳定 | 低 | 中 | 多Provider支持 + 本地fallback |
| 前端开发延期 | 中 | 中 | 优先CLI，WebUI可迭代 |
| 预测功能复杂度高 | 高 | 中 | MVP不含预测，后续迭代 |

---

## 8. 附录

### 8.1 参考资料

| 资源 | 链接 | 用途 |
|------|------|------|
| GitNexus | GitHub | 图谱可视化参考 |
| MiroFish | GitHub | 预测引擎参考 |
| D3.js | d3js.org | 图谱渲染 |
| NetworkX | networkx.org | 图计算 |
| ChromaDB | trychroma.com | 向量存储 |
| FastAPI | fastapi.tiangolo.com | API框架 |

### 8.2 术语表

| 术语 | 定义 |
|------|------|
| **知识节点** | 知识库中的一个知识点，包含内容和元数据 |
| **知识关联** | 两个知识节点之间的关系 |
| **图谱可视化** | 将知识节点和关联以图形方式展示 |
| **向量化** | 将文本转换为向量表示的过程 |
| **语义检索** | 基于向量相似度的检索方式 |

### 8.3 决策记录

| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-03-16 | MVP不含AI预测 | 技术复杂度高，2周内难以完成 |
| 2026-03-16 | 选择SQLite而非PostgreSQL | 本地优先，部署简单 |
| 2026-03-16 | D3.js而非Cytoscape.js | 社区活跃，文档完善 |

---

*PRD v1.0 — 2026-03-16 | 编写人: 小pm | 审核人: 待定*
