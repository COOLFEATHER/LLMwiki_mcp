# SCHEMA.md — Wiki 维护手册

> 本文件指导 LLM 如何编译与维护 Wiki。随使用演化，反映对领域理解的深度。
> 三层架构：Raw（不可变输入）/ Wiki（本手册约束的编译产物）/ Schema（本文件）。

## 页面类型

| type | 用途 | 何时生成 |
|---|---|---|
| concept | 概念的定义、要点、关联 | 出现反复涉及的核心概念 |
| entity | 人/物/项目等实体 | 素材中提及的具体对象 |
| summary | 对一份或多份原始素材的综合摘要 | Ingest 一份 raw 后 |
| index | 某主题下相关页导航 | 某主题页面增多时 |
| contradiction | 不同来源的冲突结论 | 检测到矛盾时 |

## frontmatter 规范

```yaml
---
title: 页面标题              # 必填
type: concept               # 必填，见上表
tags: [标签]                # 可选，列表
sources: [raw/xxx.md]       # 可选，溯源到 Raw
created: ISO8601            # 必填
updated: ISO8601            # 必填
confidence: 0.0~1.0         # 可选，默认 1.0
category: 分类              # 可选
---
```

## 命名约定

- 文件名 = 页面名，空格转下划线：`[[LLM Wiki]]` → `LLM_Wiki.md`
- 概念页用单数名词；实体页用专有名

## 双向链接

- 用 `[[页面名]]` 建立链接，Obsidian 兼容
- 每页尽量链接到 2-5 个相关概念，避免孤儿
- 矛盾用引用块标注：`> ⚠ 矛盾：[[A]] 称 X，[[B]] 称 Y`

## Ingest 工作流

1. 读取 raw 中新素材
2. 提取关键概念/实体
3. 为每个新概念/实体创建或更新页面（补摘要、加链接）
4. 检测与既有结论的矛盾，必要时生成 contradiction 页
5. 更新相关 index 页
6. 一篇素材通常触发 5-15 处页面修改
7. 写入后刷新 links.json（`links.save_graph()`）

## 质量标准

- 每页聚焦单一主题，避免大杂烩
- 概念页必有：定义句 + 要点列表 + 至少一个出链
- 摘要页必填 sources 溯源
- 矛盾页必引双方来源
