# 🧠 LLM Wiki — 轻量个人知识库 MCP Server

> **编译一次，持续复利** · 替代传统 RAG 的"每次从零检索"

**15 个源文件 · 4 个运行时依赖 · 无 PyTorch / Chroma / LangGraph**

---

## 这是什么

LLM Wiki 是一个以 **编译复利** 为核心的个人知识库工具。它将原始素材编译为带双向链接的结构化 Wiki 页面，而不是像传统 RAG 那样每次查询从零检索碎片。

```
                     ┌─ 原始素材 ──→  LLM 编译 ──→  互联 Wiki 页
  ┌─ query ────┤                                                   ├─→ 结构化回答
  └─ 检索 ──────→  BM25 + [可选向量] + RRF + 链接扩展 ──────→ 相关片段
```

可作为 **MCP Server** 接入 Claude Desktop / Cursor 等任意 MCP Agent，也自带交互式对话框。

---

## 快速开始

### 安装

```bash
pip install fastmcp openai pyyaml python-dotenv
```

或克隆后本地安装：

```bash
git clone https://github.com/COOLFEATHER/LLMwiki_mcp.git
cd LLMwiki_mcp
pip install -e .
```

### 启动对话

```bash
python3 chat.py
```

界面：

```
  ╔══════════════════════════════════════════════╗
  ║       🧠  LLM Wiki  —  个人知识库对话        ║
  ╚══════════════════════════════════════════════╝

  📡 检索:   向量 + BM25 + RRF + 链接扩展
  🎯 Embed:  本地 TF-IDF
  🤖 回答:   纯检索
  📚 Wiki:   6 页

  you> 查一下 Agent 是什么
  📄 Agent → Agent 是能感知环境、自主决策、执行动作的系统...
```

### 作为 MCP Server 启动

```bash
llm-wiki-server
```

---

## 两种回答模式

| 模式 | 命令 | 说明 |
|---|---|---|
| **纯检索**（默认） | `python3 chat.py` | 直接返回 Wiki 片段，零延迟，无需 API key |
| **LLM 回答** | `python3 chat.py --llm` | 检索后让 LLM 组织回答，更易读，需要 API key |

对话中输入 `/llm` 随时切换。

---

## 5 个 MCP 工具

| 工具 | 说明 | 需要 API key |
|---|---|---|
| `query(question)` | 混合检索 + 链接扩展，返回相关 Wiki 片段 | ❌ |
| `read_wiki(page)` | 读取 Wiki 页全文（含 frontmatter） | ❌ |
| `write_wiki(title, body, type, tags)` | 新建 Wiki 页，自动建索引 | ❌ |
| `ingest(raw_path)` | 编译原始素材为 Wiki 页（提取概念/建链/标矛盾） | ✅ |
| `rebuild_index()` | 全量重建检索索引 | ❌ |

### 直接调用示例

```python
import server

# 查知识库（无需 API key）
print(server.query("什么是 Agent"))

# 读 Wiki 页
print(server.read_wiki("LLM_Wiki"))

# 写新页（自动建索引）
server.write_wiki("设计模式", "# 设计模式\n\n正文...", tags="编程,架构")

# 编译素材（需要 API key）
print(server.ingest("data/raw/笔记.md"))
```

---

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `OPENAI_API_KEY` | — | LLM chat API key（ingest 和 --llm 模式需要） |
| `OPENAI_BASE_URL` | — | 兼容 OpenAI 接口的地址，如 `https://api.deepseek.com` |
| `CHAT_MODEL` | `deepseek-chat` | 对话模型名 |
| `EMBED_PROVIDER` | `local` | Embedding 模式：`api` / `local` / `off` |
| `EMBED_API_KEY` | — | Embedding API key（`EMBED_PROVIDER=api` 时需要） |
| `EMBED_API_URL` | — | Embedding API 地址 |
| `EMBED_MODEL` | `text-embedding-3-small` | Embedding 模型名 |

---

## Embedding 三模式

| 模式 | 设置 | 检索链路 | 依赖 | 效果 |
|---|---|---|---|---|
| **local**（默认） | `EMBED_PROVIDER=local` | TF-IDF 向量 + BM25 + RRF + 链接扩展 | 纯 numpy | 本地可用，零配置 |
| **api** | + `EMBED_API_KEY` | 语义向量 + BM25 + RRF + 链接扩展 | openai | 语义理解更好 |
| **off** | `EMBED_PROVIDER=off` | BM25 + 链接扩展 | 无 | 最轻量 |

---

## 数据架构

```
data/
├── raw/              原始素材（只增不改，不可变真源）
├── wiki/             编译产物（frontmatter + markdown）
│   ├── Agent.md
│   ├── LLM_Wiki.md
│   └── ...
├── links.json        双向链接图谱（自动维护）
└── index.json        检索索引（自动重建）
```

**三层架构**：

1. **Raw Sources** — 原始素材，不可变、可重编译
2. **Wiki** — LLM 编译产物，`[[双向链接]]` 互联，派生可重建
3. **Schema** — `SCHEMA.md` 维护手册，约束页面规范

---

## 轻量化对比

| 重量级依赖 | 本项目的替代 | 节省 |
|---|---|---|
| sentence-transformers + PyTorch (~2GB) | API embedding / 本地 TF-IDF | ~2GB |
| chromadb + duckdb (~500MB) | 扁平 JSON 向量索引（纯 Python） | ~500MB |
| langgraph + langchain-core (~50MB) | 5 个 MCP 工具直接调用 | ~50MB |
| rank-bm25 + jieba (~10MB) | 自实现 BM25（80 行） | ~10MB |
| watchdog (~1MB) | 按需重建，无常驻监听 | ~1MB |

**安装体积 < 30MB，核心代码 ~1600 行。**

---

## 设计要点

- **无 reranker**：Wiki 编译期已做整合/交叉引用/矛盾标注，检索对象是预蒸馏结构，"Wiki 即 reranker"
- **链接扩展检索**：BM25/向量找入口页 → 沿 `[[双向链接]]` 图遍历扩 N 跳，比纯语义召回更准、更可解释
- **自实现 BM25**：纯 Python ~80 行，内置中文分词 fallback，无外部依赖
- **Ingest 编译循环**：1 份原始素材 → LLM 提取概念 → 自动创建/更新 3-15 个互联 Wiki 页

---

## 接入 MCP Agent

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

## 许可证

MIT
