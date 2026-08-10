---
title: Agent
type: entity
tags:
- agent
- 范式
- mcp
- llm-wiki
sources:
- raw/sample_agent_notes.md
- raw/llmwiki项目报告.md
created: '2026-08-03T15:12:48+08:00'
updated: '2026-08-10T15:10:53+08:00'
confidence: 1.0
---

## 定义

**Agent** 指 MCP 兼容的智能体客户端，可通过 MCP stdio 协议接入 [[LLM_Wiki]] 并使用其 [[Tool_Use]]。

## 兼容 Agent

- Claude Desktop
- Cursor
- 任意 MCP 标准兼容 Agent

## 接入方式

通过 `mcpServers` JSON 配置（如 `llm-wiki-server` 命令），Agent 即可调用 [[LLM_Wiki]] 的 [[Tool_Use]] 工具集。

## 关联

- Agent 是 [[LLM_Wiki]] 的用户端
- 通过 [[MCP_Server]] 与 Wiki 交互
