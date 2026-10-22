# 投递提示词（可复制粘贴）

在任意 WorkBuddy 空间或其他 AI 工具中，学完一段内容后，复制以下提示词发给 AI：

---

```
请把以上学习内容总结成 Obsidian 格式的 markdown 笔记，保存到 ~/Desktop/LearningInbox/ 目录下。

要求：
1. 文件名用核心主题（中英文均可，单词间用连字符），扩展名 .md
2. 文件开头加 YAML frontmatter：
   ---
   title: 笔记标题
   tags: [标签1, 标签2, 标签3]
   source: 当前空间名称
   date: YYYY-MM-DD
   ---
3. 正文用 Obsidian markdown 格式：
   - 用 # ## ### 层级标题组织结构
   - 代码用 ``` 代码块
   - 重点用 **加粗** 或 > 引用
4. 内容要精炼，保留核心知识点、踩坑记录、关键结论
5. 写完后告诉我文件完整路径

示例文件 ~/Desktop/LearningInbox/Redis持久化对比.md：
---
title: Redis 持久化 RDB vs AOF
tags: [redis, 面试, 持久化]
source: Redis练功房
date: 2026-08-11
---
# Redis 持久化：RDB vs AOF
...
```

---

## 一句话精简版

如果嫌长，用这个精简版：

```
把以上学习内容总结成 Obsidian 笔记，写到 ~/Desktop/LearningInbox/ 下，文件名用主题，带 frontmatter（title/tags/source/date），正文用 markdown 格式。
```

## 提醒

- 投递后，到 AI Knowledge Hub 的 Web 界面点「扫描投递箱」即可导入
- 重复投递同一内容不会重复导入（MD5 去重）
- 原文件导入后会归档到 `data/inbox-processed/`，不会删除
