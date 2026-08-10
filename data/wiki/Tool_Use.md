---
title: Tool_Use
type: concept
tags:
- agent
- 工具
- tool-use
- mcp
sources:
- raw/sample_agent_notes.md
- raw/llmwiki项目报告.md
created: '2026-08-03T15:12:48+08:00'
updated: '2026-08-10T15:10:53+08:00'
confidence: 1.0
---

## 定义

**Tool_Use** 是 [[LLM_Wiki]] 通过 [[MCP_Server]] 暴露给 [[Agent]] 的 5 个工具及其调用机制。

## 工具列表

| 工具 | 说明 | 是否需要 API key |
|---|---|---|
| `query(question)` | 混合检索 + 链接扩展 | ❌ |
| `read_wiki(page)` | 读取 Wiki 页全文 | ❌ |
| `write_wiki(title, body, type, tags)` | 新建 Wiki 页，自动建索引 | ❌ |
| `ingest(raw_path)` | 编译素材为 Wiki 页 | ✅ |
| `rebuild_index()` | 全量重建检索索引 | ❌ |

## 设计原则

- MCP 工具职责单一，无需重量级编排框架（替代 LangGraph）
- 无状态，无常驻监听（轮询哈希判变更）
- 按需调用，适配 [[轻量化设计]]

## 关联

- [[Ingest]] 是工具之一
- 属于 [[LLM_Wiki]] 的 MCP 工具集
