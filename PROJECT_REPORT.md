# LLM Wiki — 轻量化 MCP Server 项目报告

> 版本 0.3.0 | 2026-08-10

---

## 一、项目概述

**LLM Wiki** 是一个以 LLM Wiki 模式（Karpathy 2026）为核心的个人知识库 MCP Server。它将原始素材编译为带双向链接的结构化 Wiki 页面，并对外提供 5 个 MCP 工具，可接入任意 MCP 兼容的 Agent（Claude Desktop、Cursor 等）。

项目核心差异于传统 RAG：**"编译一次、持续复利"** 替代 **"每次从零检索"**，知识在体积增长的同时理解深度也持续积累。

---

## 二、架构设计

### 2.1 三层数据架构

```
┌─────────────────────────────────────────────────────┐
│  Raw Sources  (data/raw/) — 不可变输入，只增不改    │
│  原始素材：文章、笔记、对话记录                      │
├─────────────────────────────────────────────────────┤
│  Wiki  (data/wiki/) — LLM 编译产物，可重建          │
│  概念页 / 实体页 / 摘要页 / 索引页 / 矛盾标注页     │
│  [[双向链接]] 互联，frontmatter 元数据               │
├─────────────────────────────────────────────────────┤
│  Schema  (SCHEMA.md) — 维护手册，随使用演化          │
│  页面规范 / 命名约定 / 编译工作流 / 质量标准          │
└─────────────────────────────────────────────────────┘
```

- **Raw 不可变**：原始素材是唯一真源，支持重编译
- **Wiki 可重建**：派生产物丢失可从 Raw + Schema 重建
- **Schema 约束质量**：规范页面类型、frontmatter 字段、链接语法

### 2.2 核心引擎：Ingest 编译循环

```
原始素材 → LLM 读取 → 提取概念/实体
  → 创建/更新多个 Wiki 页
  → 建立 [[双向链接]] 互联
  → 检测与既有结论的矛盾并标注
  → 更新 links.json 双向链接图谱
  → 重建检索索引
```

一份素材可触发 3-15 处 Wiki 页修改，将散落知识编译为互联网络。

### 2.3 检索流水线

```
query ─┬─ [可选] 向量检索（API / 本地 TF-IDF）──┐
       │                                           │
       └─ BM25（自实现，纯 Python）──────────────┤
                                                  │
                    RRF 融合 → top_k → 沿 [[链接]] 扩 N 跳
```

三种 Embedding 模式可选：

| 模式 | 配置 | 检索链路 | 依赖 |
|---|---|---|---|
| `local`（默认） | — | TF-IDF 向量 + BM25 + RRF + 链接扩展 | 纯 numpy |
| `api` | + API key | 语义向量 + BM25 + RRF + 链接扩展 | openai |
| `off` | — | BM25 + 链接扩展（最轻量） | 无 |

无需 reranker：Wiki 编译期已做整合/交叉引用/矛盾标注，检索对象是预蒸馏结构化内容。

---

## 三、轻量化设计

相比 v0.2 骨架版本，本版本做了彻底轻量化：

| 删除的重量级依赖 | 替代方案 | 节省 |
|---|---|---|
| sentence-transformers + PyTorch | API embedding / 本地 TF-IDF | ~2GB |
| chromadb + duckdb | 扁平 JSON 向量索引（60 行） | ~500MB |
| langgraph + langchain-core | 5 个 MCP 工具直接调用 | ~50MB |
| rank-bm25 + jieba | 自实现 BM25（80 行） | ~10MB |
| watchdog | 按需重建，无常驻监听 | ~1MB |
| 记忆系统（4 模块） | MCP 无状态 | — |

**安装体积从 ~2.5GB → < 30MB，核心代码 1587 行。**

---

## 四、MCP 工具

| 工具 | 说明 | 是否需要 API key |
|---|---|---|
| `query(question)` | 混合检索 + 链接扩展 | ❌ |
| `read_wiki(page)` | 读取 Wiki 页全文 | ❌ |
| `write_wiki(title, body, type, tags)` | 新建 Wiki 页，自动建索引 | ❌ |
| `ingest(raw_path)` | 编译素材为 Wiki 页 | ✅ |
| `rebuild_index()` | 全量重建检索索引 | ❌ |

可通过 MCP stdio 协议接入任意 Agent：

```json
{
  "mcpServers": {
    "llm-wiki": {
      "command": "llm-wiki-server",
      "env": {
        "OPENAI_API_KEY": "sk-...",
        "OPENAI_BASE_URL": "https://api.deepseek.com"
      }
    }
  }
}
```

---

## 五、文件结构

```
llmwiki/
├── server.py           # MCP 入口（5 个工具，246 行）
├── chat.py             # 交互式对话框（429 行）
├── app/
│   ├── config.py       # 路径/模型/检索参数
│   ├── bm25.py         # 自实现 BM25（纯 Python，80 行）
│   ├── embed.py        # Embedding 接口（api/local/off 三模式）
│   ├── vectordb.py     # 扁平 JSON 向量索引（替代 Chroma）
│   ├── rag/
│   │   └── chunker.py  # Markdown 结构化切片
│   └── wiki/
│       ├── schema.py   # 页面类型与 frontmatter 校验
│       ├── page.py     # WikiPage 数据模型
│       ├── storage.py  # md 文件读写
│       ├── metadata.py # 时间戳与 frontmatter 生成
│       ├── links.py    # 双向链接图谱
│       └── ingest.py   # 编译循环引擎
├── data/               # 运行时数据（gitignore）
├── requirements.txt    # 4 个轻依赖
├── pyproject.toml      # pip install -e . 打包
└── SCHEMA.md           # Wiki 维护手册
```

---

## 六、技术决策

| 决策 | 理由 |
|---|---|
| 无 PyTorch / Chroma / LangGraph | MCP 工具职责单一，无需重量级编排和向量数据库 |
| 自实现 BM25（非 rank-bm25） | 去掉一个外部依赖，内置中文分词 fallback |
| 扁平 JSON 索引（非 Chroma） | 几百页量级暴力余弦 < 10ms，省去 duckdb 嵌入 |
| Embedding 三模式 | 用户按需选择，api/local/off 清晰可预期 |
| 无 reranker | 编译期已做整合，检索对象是预蒸馏结构 |
| 轮询哈希判变更（非 watchdog） | MCP 工具按需调用，无常驻监听 |

---

## 七、使用方式

```bash
# 交互式对话
python3 chat.py

# 作为 MCP Server 启动
llm-wiki-server

# 直接调用工具
python3 -c "import server; print(server.query('什么是 Agent'))"
```

---

## 八、交付清单

| 指标 | 数值 |
|---|---|
| 核心代码行 | 1,587 行 |
| 源文件数 | 18 个 |
| 总文件数（含数据） | 31 个 |
| 磁盘占用 | 184 KB |
| 运行时依赖 | 4 个 |
| MCP 工具 | 5 个 |
| Embedding 模式 | 3 种（api/local/off） |
| 安装体积 | < 30 MB |

---

## 九、简历项目经历

> 以下内容可直接用于简历。

---

### 精简版（4 bullet，适合贴简历）

**LLM Wiki MCP Server —— 轻量个人知识库编译引擎** ｜ 独立开发 ｜ Python · MCP · BM25 · RRF ｜ 2026.07–08

- 以 LLM Wiki（Karpathy 模式）为核心实现个人知识库 MCP Server：三层架构（Raw 不可变真源 / Wiki 编译产物 / Schema 维护手册），Ingest 编译循环使 1 份素材自动编译为 3-15 个互联 Wiki 页，知识从堆叠文件变为生长网络。
- 自研轻量检索引擎：自实现 BM25（纯 Python，内置中文分词 fallback）+ 扁平 JSON 向量索引（替代 Chroma）+ RRF 融合 + 双向链接图遍历，支持 api/local/off 三种 Embedding 模式按需切换。
- 彻底轻量化：砍掉 PyTorch（2GB）、Chroma（500MB）、LangGraph（50MB）等重量级依赖，安装体积从 ~2.5GB 降至 < 30MB，核心代码仅 1,587 行。
- 标准 MCP Server 打包，5 个工具（query/read_wiki/write_wiki/ingest/rebuild_index）可接入任意 MCP Agent（Claude Desktop、Cursor 等），随附交互式对话框。

### 设计亮点（面试可展开）

1. **编译复利替代无状态 RAG**：传统 RAG 每次从零检索碎片，本系统将知识"编译一次、持续更新"，使查询走预蒸馏结构化页面而非原始碎片。
2. **砍 reranker 的正当性论证**：Wiki 编译期已做整合/交叉引用/矛盾标注，检索对象本身就是预计算结构——"Wiki 即 reranker"。
3. **链接扩展检索**：向量/BM25 找入口页 → 沿双向链接图遍历扩 N 跳，比纯语义召回更准、更可解释。
4. **Embedding 可插拔**：三模式 api/local/off 由环境变量控制，用户按需选择，不冗余不缺失。
