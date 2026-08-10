---
title: Ingest
type: concept
tags:
- 编译
- ingest
- 编译引擎
- llm-wiki
sources:
- raw/llmwiki项目报告.md
created: '2026-08-03T15:02:56+08:00'
updated: '2026-08-10T15:10:53+08:00'
confidence: 1.0
---

## 定义

**Ingest** 是 [[LLM_Wiki]] 的编译循环引擎，将原始素材编译为互联的 Wiki 页网络，是项目核心的 "编译" 能力实现。

## 编译流程

```
原始素材 → LLM 读取 → 提取概念/实体
  → 创建/更新多个 Wiki 页
  → 建立 [[双向链接]] 互联
  → 检测与既有结论的矛盾并标注
  → 更新 links.json 双向链接图谱
  → 重建检索索引
```

## 关键特性

- 一份素材触发 **3-15 处** Wiki 页修改
- 受 [[三层架构]] 中的 Schema 层约束（SCHEMA.md 维护手册）
- Raw 不可变：原始素材是唯一真源，支持重编译
- Wiki 可重建：派生产物可从 Raw + Schema 重建

## 作为 MCP 工具

`ingest(raw_path)` 是 [[LLM_Wiki]] 的 5 个 [[Tool_Use]] 工具之一，需要 API key 用于 LLM 编译。

## 关联

- [[Tool_Use]]：ingest 是工具列表之一
- [[编译复利]]：Ingest 是实现编译复利的核心机制
