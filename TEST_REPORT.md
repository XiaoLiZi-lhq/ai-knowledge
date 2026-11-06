# AI Knowledge Hub - 测试报告与使用指南

## 测试结果总览

| 端点 | 功能 | 状态 | 说明 |
|------|------|------|------|
| `GET /api/v1/health` | 健康检查 | ✅ 通过 | Ollama + ChromaDB 均连接正常 |
| `POST /api/v1/chat` | RAG 知识库问答 | ✅ 通过 | 基于笔记内容准确回答 |
| `POST /api/v1/quiz/generate` | AI 出题 | ✅ 通过 | 生成结构化选择题+简答题 |
| `GET /api/v1/gaps/scan` | 知识盲区扫描 | ✅ 通过 | 5 领域 30 个盲区识别 |

## 本轮修复清单

### 1. Ollama qwen3.5:9b 空回复问题
**问题**: 使用 OpenAI 兼容 API 时，qwen3.5 把输出放在 `thinking` 字段，`num_predict: 100` 被思考 token 全部消耗
**修复**: 改用 Ollama 原生 `/api/chat` API + `"think": False` 参数

### 2. Embedding 三级降级
**问题**: Ollama `nomic-embed-text` 拉不下来（DNS 超时），sentence-transformers 被 HuggingFace 代理 502 挡住
**修复**: 新增零依赖本地嵌入引擎（jieba 分词 + 字符 n-gram + 哈希向量），384 维 L2 归一化

### 3. routes.py Depends 缺失
**问题**: `from fastapi import` 未导入 `Depends`
**修复**: 补全导入

### 4. JSON 解析失败
**问题**: LLM 返回的 JSON 字符串值内含未转义换行符
**修复**: 添加 `fix_newlines_in_strings` 字符级状态机修复函数

### 5. SQLite 表不存在
**问题**: `_log_quiz` 访问 `learning_log` 表但数据库未初始化
**修复**: 新增 `scripts/init_db.py` 初始化脚本 + 服务启动时自动执行 + 容错 try/except

## 启动方式

```bash
cd /Users/lihongqin/WorkBuddy/Claw/outputs/ai-knowledge-hub

# 激活虚拟环境
source .venv/bin/activate

# 启动服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 或开发模式（热重载）
python -m uvicorn app.main:app --reload --port 8000
```

## API 文档
启动后访问: http://localhost:8000/docs

## 待办事项
- [ ] 填入 DeepSeek API Key（作为 Ollama 降级备用）
- [ ] 填入微信 wxid（微信白名单）
- [ ] 后续可尝试在好的网络环境下 `ollama pull nomic-embed-text`（替换本地嵌入引擎）
- [ ] 配置 Obsidian Git 插件实现自动备份

## 检索质量评测记录（scripts/eval_rag.py）

**口径**：24 道真实 Java 面试题 → 按预期笔记标题匹配 top-5 检索结果；Hit@5 = 命中题目占比，MRR@5 = 预期笔记排名倒数的均值。**度量的是检索质量，不是回答准确率。**

### 运行记录

| 日期 | Hit@5 | MRR@5 | 未命中 | 环境 |
|---|---|---|---|---|
| 2026-10-22 | 95.8% (23/24) | 0.861 | TCP 三次握手 | Ollama nomic-embed-text（768 维） |
| **2026-11-06** | **91.7% (22/24)** | **0.847** | TCP 三次握手；线程池核心参数 | Ollama nomic-embed-text（768 维），当前索引 |

### 2026-11-06 运行明细（未命中分析）

- ❌ **TCP 三次握手四次挥手**：知识库无计算机网络专题笔记（已知盲区，评测集故意保留以暴露盲区）；
- ❌ **线程池的核心参数和工作流程**：`JavaSE-10多线程与反射` 未进 top-5——当前索引较 10 月新增了秒杀系统、七天速成等综合类笔记，召回池被非核心笔记挤占（改进方向：检索加 source/type 过滤或调大 BM25 权重）；
- 其余 22 题命中，其中 19 题预期笔记排名 top-1。

### 复现方式

```bash
source .venv/bin/activate
python scripts/eval_rag.py            # 默认 top_k=5
python scripts/eval_rag.py --topk 3   # 改 top-k
```

依赖：Ollama 运行中（`nomic-embed-text` + 生成模型）、`data/chroma` 索引已建立（路径来自 `.env` 的 `CHROMA_PERSIST_PATH`）。预期输出：逐题 ✅/❌ 明细 + 末尾两行 `Hit@5 / MRR@5` 汇总。
