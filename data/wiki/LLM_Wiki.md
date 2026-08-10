---
title: LLM_Wiki
type: entity
tags:
- 知识库
- RAG
- 编译
- llm-wiki
- mcp
- 个人wiki
sources:
- raw/llmwiki项目报告.md
created: 2026-08-03 14:55:00+08:00
updated: '2026-08-10T15:10:53+08:00'
confidence: 1.0
---

## 定义

**LLM Wiki** 是一个以 LLM Wiki 模式（Karpathy 2026）为核心的个人知识库 [[MCP_Server]]，版本 0.3.0（2026-08-10）。它将原始素材编译为带 [[双向链接]] 的结构化 Wiki 页面，可接入任意 MCP 兼容的 [[Agent]]。

## 核心特性

- 核心代码 **1,587 行**，源文件 18 个，磁盘占用 184 KB
- 安装体积 **< 30 MB**，运行时依赖仅 4 个
- 对外提供 **5 个 [[Tool_Use]] 工具**：query / read_wiki / write_wiki / ingest / rebuild_index

## 数据架构

采用 [[三层架构]]：Raw（不可变真源）/ Wiki（编译产物）/ Schema（维护手册），由 [[Ingest]] 编译循环驱动。

## 核心差异

与 [[RAG]] 的关键不同：**"编译一次、持续复利"**（[[编译复利]]）替代 **"每次从零检索"**，知识在体积增长的同时理解深度也持续积累。

## 检索引擎

- 自实现 [[BM25]]（纯 Python，80 行，内置中文分词 fallback）
- 三种 [[Embedding]] 模式：api / local / off，按需切换
- [[RRF]] 融合 + [[链接扩展]]（沿双向链接图遍历扩 N 跳）
- 扁平 JSON 向量索引（替代 Chroma，60 行）

## 使用方式

```bash
# 交互式对话
python3 chat.py

# 作为 MCP Server 启动
llm-wiki-server
```

## 设计亮点

1. **Wiki 即 reranker**：编译期已做整合/交叉引用/矛盾标注，无需额外 reranker
2. **Embedding 可插拔**：三模式 api/local/off 由环境变量控制
3. **[[轻量化设计]]**：砍掉 PyTorch（~2GB）、Chroma（~500MB）、LangGraph（~50MB）等重量级依赖
