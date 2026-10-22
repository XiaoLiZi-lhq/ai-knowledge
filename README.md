# AI Knowledge Hub - 个人AI知识中台

以 Obsidian 为底座，集成 Ollama 本地大模型（qwen3.5:9b 生成 + nomic-embed-text 向量化），支持 RAG 知识库问答、GitHub 热点收集、微信双向对话、AI 导师学习辅助。

## 架构与关键设计

```
Obsidian Vault (120+ 篇 Java 后端笔记)
   │  MarkdownChunker 按标题+滑动窗口分块
   ▼
ChromaDB 向量库 (nomic-embed-text 768维, 三级降级: Ollama → sentence-transformers → 本地哈希引擎)
   │
   ▼  检索: 三层漏斗
   │   1. 向量召回 Top-20 (HNSW)
   │   2. BM25 重排 (jieba 分词 + 候选池局部 IDF, k1=1.5 b=0.75)
   │   3. 距离阈值过滤 → Top-K
   ▼
Ollama qwen3.5:9b 生成 (SSE 流式输出 / JSON 出题)
```

**检索质量评测**（`scripts/eval_rag.py`，24 道真实 Java 面试题，2026-10-22）：

| 指标 | 数值 | 说明 |
|---|---|---|
| Hit@5 | **95.8%** (23/24) | 前 5 条检索结果含正确笔记 |
| MRR@5 | **0.861** | 正确笔记平均排名倒数 |

> 唯一未命中项（TCP 三次握手）因知识库暂无计算机网络专题笔记——评测同时暴露了笔记盲区。

## 快速开始

```bash
# 1. 克隆仓库
git clone <your-repo-url> ai-knowledge-hub
cd ai-knowledge-hub

# 2. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Mac/Linux
# .venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API Key 和路径

# 5. 确保 Ollama 运行
OLLAMA_ORIGINS="*" ollama serve &
ollama pull qwen3.5:9b
ollama pull nomic-embed-text

# 6. 初始化 Obsidian Vault 结构
python scripts/init_vault.py --path ~/Documents/MyVault

# 7. 启动服务
python -m app.main
```

## 项目结构

```
ai-knowledge-hub/
├── app/                    # 主应用
│   ├── main.py            # FastAPI 入口
│   ├── api/               # API 路由
│   ├── core/              # 核心逻辑（RAG/LLM/嵌入）
│   ├── services/          # 业务服务
│   └── integrations/      # 微信/飞书集成
├── config/                # 配置
├── data/                  # 运行时数据
├── scripts/               # 脚本
└── tests/                 # 测试
```

## 核心功能

- RAG 知识库问答（Ollama qwen3.5:9b 本地生成，DeepSeek 备用，SSE 流式输出）
- 混合检索：向量召回 + jieba BM25 重排（中文查询有效）
- 检索质量可度量：内置评测脚本（Hit@5 / MRR@5）
- GitHub Trending 每日自动收集
- 微信双向对话（指令系统）
- AI 导师（出题/盲区扫描/学习计划）
- Obsidian Vault 自动整理（打标/分类/双链）
- 桌面投递箱（LearningInbox 笔记快速导入）
- Git 自动备份到 GitHub

## 评测与验证

```bash
# 跑检索评测（需先完成索引）
python scripts/eval_rag.py

# 跑测试
python -m pytest tests/ -q
```

## 提交规范

每次代码改动通过 `scripts/git-commit.sh` 提交，自动附带规范的提交说明。
