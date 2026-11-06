# AI Knowledge Hub - 个人AI知识中台

以 Obsidian 为底座，集成 Ollama 本地大模型（qwen3.5:9b 生成 + nomic-embed-text 向量化），支持 RAG 知识库问答、GitHub 热点收集、微信双向对话、AI 导师学习辅助。

> **30 秒了解**：把 Obsidian 里的 120+ 篇学习笔记变成可问答的本地知识库——Markdown 切分 → 向量化 → ChromaDB 混合检索（向量召回 + BM25 重排）→ Ollama 本地模型生成（可选 DeepSeek 备用）。亮点是 **embedding 三级降级**（Ollama → sentence-transformers → 零依赖本地哈希），任一引擎不可用时检索链路仍全通；检索质量用 24 道真实面试题度量（Hit@5 / MRR@5，见下方评测表）。

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

**检索质量评测**（`scripts/eval_rag.py`，24 道真实 Java 面试题，最近一次运行 2026-11-06）：

| 指标 | 数值 | 说明 |
|---|---|---|
| Hit@5 | **91.7%** (22/24) | 前 5 条检索结果含预期笔记 |
| MRR@5 | **0.847** | 预期笔记平均排名倒数 |

> 口径：按「预期笔记标题」匹配 top-5 检索结果，度量**检索质量而非回答准确率**。未命中 2 题：TCP 三次握手（知识库暂无计算机网络专题笔记）、线程池核心参数（多线程笔记未进 top-5）。历史运行与逐题明细见 [TEST_REPORT.md](TEST_REPORT.md)。

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

## API 一览

所有业务端点需携带 `Authorization: Bearer $API_KEY`（`/api/v1/health` 除外）。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/health` | 健康检查（含 `embedding` 字段：当前可用引擎/维度、notes 集合绑定引擎、是否降级） |
| POST | `/api/v1/documents/upload` | **文档上传**（multipart/form-data，字段 `file`）：`.md`/`.txt`，单文件 ≤2MiB；落盘 `data/uploads/` → MarkdownChunker 切分 → 嵌入 → ChromaDB `notes` 集合入库（`origin=upload`）。返回 `{document_id, filename, chunks, embedding_engine, embedding_dim, collection, status}` |
| GET | `/api/v1/documents` | 列出已上传文档（document_id/文件名/块数/上传时间） |
| DELETE | `/api/v1/documents/{document_id}` | 删除该上传文档的全部向量（不影响 Vault 笔记），返回 `{deleted_chunks}` |
| POST | `/api/v1/chat` | RAG 知识库问答（检索 Vault 笔记 + 上传文档，增强生成） |
| POST | `/api/v1/chat/stream` | 同上，SSE 流式输出 |
| POST | `/api/v1/notes/sync` | 触发 Vault 向量化同步（含孤儿向量清理，返回 `{synced_chunks, indexed, failed_files, orphan_chunks_removed, ...}`） |
| POST | `/api/v1/quiz/generate` / `/quiz/submit` | AI 出题 / 提交答案 |
| GET | `/api/v1/gaps/scan` · POST `/api/v1/plan/generate` | 知识盲区扫描 / 学习计划 |
| GET | `/api/v1/hot/today` · POST `/api/v1/hot/collect` | GitHub 热点 |
| POST | `/api/v1/notes/organize` | AI 整理笔记 |
| POST | `/api/v1/sync/workbuddy`（+ `/preview`）· POST `/api/v1/sync/inbox`（+ `/preview`） | 跨空间同步 / 投递箱导入 |
| GET | `/api/v1/learning/stats` | 学习行为统计 |
| POST | `/api/v1/wechat/message` | 微信桥接 |

上传示例：

```bash
curl -X POST -H "Authorization: Bearer $API_KEY" \
  -F "file=@notes.md" http://127.0.0.1:8000/api/v1/documents/upload
curl -X POST -H "Authorization: Bearer $API_KEY" -H 'Content-Type: application/json' \
  -d '{"query":"刚上传的文档讲了什么"}' http://127.0.0.1:8000/api/v1/chat
```

### 嵌入三级降级与维度一致性（R2）

- **三级引擎**：`ollama:nomic-embed-text`(768 维) → `st:bge-small-zh-v1.5`(512 维) → 自研 `local:hash-384`(384 维，零依赖兜底)；任一级失败自动降级，全程 WARNING 日志，`/health` 的 `embedding` 字段实时暴露降级状态。
- **客户端自动分批**：`/api/embed` 按批 ≤64 条（`EMBED_BATCH_SIZE`，上限 128）分批请求，规避 Ollama 批量 ≥256 的 HTTP 400。
- **集合引擎绑定（engine pin）**：每个集合的 `embedding_engine`/`embedding_dim` 写入 ChromaDB 集合 metadata，读写两端统一走 `embed_for_collection`，查询向量与集合永远同维度，杜绝混写导致的 `InvalidArgumentError`；存量集合首次访问自动按现存向量维度迁移绑定。
- **auto（默认）降级重建**：绑定引擎不可用时清库全源重嵌入换绑（Vault + uploads），旧数据不丢；**strict**（`EMBED_FALLBACK=strict`）模式直接 503 明确报错，绝不混写。
- **测试/演示开关**：`EMBED_DISABLE_ST=1` 确定性禁用 L2；`OLLAMA_EMBED_BASE_URL` 可仅将嵌入端点指向死端口（生成不受影响）模拟外部嵌入宕机。

## 核心功能

- RAG 知识库问答（Ollama qwen3.5:9b 本地生成，DeepSeek 备用，SSE 流式输出）
- 文档上传即索引：`POST /api/v1/documents/upload` 打通 上传→切分→本地嵌入→向量检索→增强生成 完整链路（无 Ollama 环境自动落到自研 384 维引擎，链路仍全通）
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
